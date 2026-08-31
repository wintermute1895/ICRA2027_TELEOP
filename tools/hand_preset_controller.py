#!/usr/bin/env python3
"""Independent keyboard controller for a binary gripper-like hand.

This process owns its own terminal.  It never reads the capture recorder's
stdin and never opens CAN; commands go through the existing hand_adapter.
Press ``f`` to advance the configured preset cycle and ``q`` to quit.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import termios
import time
import tty
from contextlib import suppress
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    # JSON is the default so this tool works with the system Python alone.
    # YAML remains accepted when PyYAML is available for local customization.
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - optional convenience
            raise SystemExit("config is not JSON and PyYAML is unavailable; use the supplied JSON config") from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise SystemExit(f"hand preset config must be a mapping: {path}")
    return value


def validate_config(config: dict[str, Any], arm: str | None = None) -> dict[str, Any]:
    selected_arm = arm or str(config.get("arm", "right"))
    hands = config.get("hands", {})
    if not isinstance(hands, dict) or selected_arm not in hands:
        raise SystemExit(f"no hand configuration for arm={selected_arm}")
    hand = hands[selected_arm]
    if not isinstance(hand, dict):
        raise SystemExit(f"hand configuration for {selected_arm} must be a mapping")
    presets = hand.get("presets")
    cycle = hand.get("cycle")
    if not isinstance(presets, dict) or not isinstance(cycle, list) or not cycle:
        raise SystemExit(f"hand {selected_arm} requires presets and a non-empty cycle")
    normalized: dict[str, Any] = {"arm": selected_arm, **hand}
    normalized_presets: dict[str, dict[str, Any]] = {}
    for name, preset in presets.items():
        if not isinstance(preset, dict):
            raise SystemExit(f"preset {name!r} must be a mapping")
        positions = preset.get("positions")
        state = preset.get("gripper_state")
        if not isinstance(positions, list) or not positions:
            raise SystemExit(f"preset {name!r} requires positions")
        if state not in (0, 1):
            raise SystemExit(f"preset {name!r} gripper_state must be 0 or 1")
        values = [float(value) for value in positions]
        if not all(math.isfinite(value) and 0.0 <= value <= 255.0 for value in values):
            raise SystemExit(f"preset {name!r} positions must be finite values in [0,255]")
        normalized_presets[str(name)] = {"positions": values, "gripper_state": int(state)}
    for name in cycle:
        if str(name) not in normalized_presets:
            raise SystemExit(f"cycle references unknown preset {name!r}")
    normalized["presets"] = normalized_presets
    normalized["cycle"] = [str(name) for name in cycle]
    normalized.setdefault("robot_namespace", "/robot1")
    normalized.setdefault("teleop_namespace", "/teleop")
    normalized.setdefault("publish_hz", 20.0)
    normalized.setdefault("hold_seconds", 0.5)
    normalized.setdefault("state_publish_hz", 2.0)
    normalized.setdefault("state_timeout_s", 2.0)
    return normalized


def next_preset(cycle: list[str], index: int) -> tuple[int, str]:
    next_index = (index + 1) % len(cycle)
    return next_index, cycle[next_index]


def _topic(config: dict[str, Any], key: str, default: str) -> str:
    value = config.get(key)
    return str(value) if value else default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/hand_presets.json"))
    parser.add_argument("--arm", choices=("left", "right"))
    parser.add_argument("--execute", action="store_true", help="allow publishing hand commands")
    parser.add_argument("--physical-estop-ready", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    config = validate_config(load_config(args.config), args.arm)
    arm = config["arm"]
    robot_ns = str(config["robot_namespace"]).rstrip("/")
    teleop_ns = str(config["teleop_namespace"]).rstrip("/")
    command_topic = _topic(config, "command_topic", f"{robot_ns}/{arm}_hand/control_cmd")
    state_topic = _topic(config, "state_topic", f"{robot_ns}/{arm}_hand/joint_states")
    gripper_topic = _topic(config, "gripper_state_topic", f"{teleop_ns}/{arm}/gripper_state")
    if args.execute and (not args.physical_estop_ready or args.confirm != "EXECUTE_HAND_PRESET_WITH_ESTOP_READY"):
        raise SystemExit("execution requires --physical-estop-ready and --confirm EXECUTE_HAND_PRESET_WITH_ESTOP_READY")
    if not sys.stdin.isatty():
        raise SystemExit("hand preset controller requires an interactive TTY")

    import rclpy
    from sensor_msgs.msg import JointState
    from std_msgs.msg import UInt8

    rclpy.init()
    node = rclpy.create_node("hand_preset_controller")
    command_pub = node.create_publisher(JointState, command_topic, 10) if args.execute else None
    state_pub = node.create_publisher(UInt8, gripper_topic, 10)
    latest_state: list[JointState] = []
    node.create_subscription(JointState, state_topic, lambda msg: latest_state.append(msg), 10)
    cycle = config["cycle"]
    presets = config["presets"]
    index = -1
    current_state: int | None = None
    print(f"[HAND] arm={arm} | f=next preset | q=quit | binary state 0=open 1=closed", flush=True)
    print(f"[HAND] cycle: {' -> '.join(cycle)} | execute={'yes' if args.execute else 'no'}", flush=True)

    def publish_state() -> None:
        if current_state is None:
            return
        message = UInt8()
        message.data = current_state
        state_pub.publish(message)

    def send_preset(name: str) -> None:
        nonlocal current_state
        preset = presets[name]
        if command_pub is None:
            print(f"\n[HAND DRY-RUN] {name} state={preset['gripper_state']} positions={preset['positions']}", flush=True)
            return
        expected = len(preset["positions"])
        if not latest_state:
            deadline = time.monotonic() + float(config["state_timeout_s"])
            while time.monotonic() < deadline and rclpy.ok() and not latest_state:
                rclpy.spin_once(node, timeout_sec=0.05)
        if not latest_state:
            print(f"\n[HAND] no state received on {state_topic}; command skipped", flush=True)
            return
        # Vendor feedback may contain passive/derived channels (the installed
        # O6 reports 11 state values while accepting 6-value commands).  The
        # command vector is validated against the configured preset; state
        # length is intentionally not required to match it.
        if not latest_state[-1].position:
            print(f"\n[HAND] empty state on {state_topic}; command skipped", flush=True)
            return
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.position = list(preset["positions"])
        message.velocity = [float(config.get("speed", 40.0))] * expected
        message.effort = [float(config.get("force", 40.0))] * expected
        end = time.monotonic() + float(config["hold_seconds"])
        period = 1.0 / float(config["publish_hz"])
        while time.monotonic() < end and rclpy.ok():
            command_pub.publish(message)
            rclpy.spin_once(node, timeout_sec=0.0)
            time.sleep(period)
        current_state = int(preset["gripper_state"])
        publish_state()
        print(f"\n[HAND] sent {name} state={current_state}", flush=True)

    fd = sys.stdin.fileno()
    old_tty = termios.tcgetattr(fd)
    state_period = 1.0 / float(config["state_publish_hz"])
    next_state = 0.0
    try:
        tty.setcbreak(fd)
        while rclpy.ok():
            now = time.monotonic()
            if now >= next_state:
                publish_state()
                next_state = now + state_period
            rclpy.spin_once(node, timeout_sec=0.01)
            import select
            ready, _, _ = select.select([fd], [], [], 0.02)
            if not ready:
                continue
            key = os.read(fd, 1).decode("utf-8", errors="ignore").lower()
            if key == "q":
                break
            if key != "f":
                continue
            index, name = next_preset(cycle, index)
            send_preset(name)
    finally:
        with suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old_tty)
        node.destroy_node()
        rclpy.shutdown()
    print("\n[HAND] controller exited; no further commands will be sent", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
