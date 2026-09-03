#!/usr/bin/env python3
"""Independent keyboard controller for a binary gripper-like hand.

This process owns its own terminal. It never reads the capture recorder's
stdin. The direct O6 backend reuses the same repository SDK as
``hand_gesture_player.py`` while publishing ROS evidence topics. Press ``f``
to advance the configured preset cycle and ``q`` to quit.
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


# Executing this file by path makes Python use tools/ as sys.path[0]. Add the
# repository root so the project-level src.hand adapter is always importable,
# independent of the caller's shell, Conda state, or current directory.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    value["_config_dir"] = str(path.resolve().parent)
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
    gesture_file = hand.get("gesture_file")
    if gesture_file is not None:
        gesture_path = Path(str(gesture_file))
        if not gesture_path.is_absolute():
            gesture_path = Path(str(config.get("_config_dir", "."))) / gesture_path
        gesture_data = json.loads(gesture_path.read_text(encoding="utf-8"))
        if str(gesture_data.get("hand", "")).upper() != str(hand.get("model", "")).upper():
            raise SystemExit(f"gesture file model does not match hand {selected_arm}: {gesture_path}")
        gestures = gesture_data.get("gestures", {})
        if not isinstance(cycle, list) or not cycle:
            raise SystemExit(f"hand {selected_arm} requires a non-empty cycle")
        presets = {}
        normalized_cycle = []
        for step in cycle:
            if not isinstance(step, dict) or "gesture_id" not in step:
                raise SystemExit("gesture-file cycles require gesture_id and gripper_state per step")
            gesture_id = str(step["gesture_id"])
            name = str(step.get("name", f"gesture_{gesture_id}"))
            if gesture_id not in gestures:
                raise SystemExit(f"cycle references missing gesture {gesture_id!r}")
            presets[name] = {"positions": gestures[gesture_id], "gripper_state": step.get("gripper_state")}
            normalized_cycle.append(name)
        cycle = normalized_cycle
    if not isinstance(presets, dict) or not isinstance(cycle, list) or not cycle:
        raise SystemExit(f"hand {selected_arm} requires presets and a non-empty cycle")
    normalized: dict[str, Any] = {"arm": selected_arm, **hand}
    position_encoding = str(hand.get("position_encoding", "raw_0_255"))
    if position_encoding not in {"raw_0_255", "normalized_0_100"}:
        raise SystemExit(f"unsupported position_encoding for {selected_arm}: {position_encoding}")
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
        source_values = [float(value) for value in positions]
        maximum = 100.0 if position_encoding == "normalized_0_100" else 255.0
        if not all(math.isfinite(value) and 0.0 <= value <= maximum for value in source_values):
            raise SystemExit(f"preset {name!r} positions must be finite values in [0,{maximum:g}]")
        values = [round(value * 255.0 / 100.0) for value in source_values] if position_encoding == "normalized_0_100" else source_values
        normalized_presets[str(name)] = {
            "positions": values,
            "source_positions": source_values,
            "gripper_state": int(state),
        }
    for name in cycle:
        if str(name) not in normalized_presets:
            raise SystemExit(f"cycle references unknown preset {name!r}")
    normalized["presets"] = normalized_presets
    normalized["cycle"] = [str(name) for name in cycle]
    normalized["position_encoding"] = position_encoding
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


def classify_hand_key(key: str) -> str:
    """Classify one hand-controller key without touching ROS or a TTY."""
    value = str(key).lower()
    if value == "f":
        return "preset"
    if value == "q":
        return "quit"
    return "ignore"


def cached_o6_angles(hand: Any) -> list[float] | None:
    """Read the linkerbot O6 polling cache without blocking keyboard input."""
    snapshot = hand.get_snapshot()
    angle_data = getattr(snapshot, "angle", None)
    angles = getattr(angle_data, "angles", None)
    if angles is None or not hasattr(angles, "to_list"):
        return None
    values = [float(value) for value in angles.to_list()]
    if len(values) != 6 or not all(math.isfinite(value) and 0.0 <= value <= 100.0 for value in values):
        return None
    return values


def _topic(config: dict[str, Any], key: str, default: str) -> str:
    value = config.get(key)
    return str(value) if value else default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/hand_presets.json"))
    parser.add_argument("--arm", choices=("left", "right"))
    parser.add_argument("--backend", choices=("ros", "direct-o6"), default="ros")
    parser.add_argument("--can", default="can0", help="SocketCAN interface for the direct O6 backend")
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
    gripper_state_pub = node.create_publisher(UInt8, gripper_topic, 10)
    joint_state_pub = node.create_publisher(JointState, state_topic, 10) if args.backend == "direct-o6" else None
    latest_state: JointState | None = None
    state_subscription = None
    if args.backend == "ros":
        def on_state(msg: JointState) -> None:
            nonlocal latest_state
            latest_state = msg
        state_subscription = node.create_subscription(
            JointState, state_topic, on_state, 10
        )
    cycle = config["cycle"]
    presets = config["presets"]
    index = -1
    current_state: int | None = None
    direct_hand = None
    joint_names: list[str] = []
    if args.backend == "direct-o6":
        if str(config.get("model", "")).upper() != "O6":
            raise SystemExit("the direct-o6 backend requires an O6 hand configuration")
        if config["position_encoding"] != "normalized_0_100":
            raise SystemExit("the direct-o6 backend requires normalized_0_100 presets")
        if not args.execute:
            raise SystemExit("the direct-o6 backend is hardware-only and requires --execute")
        from src.hand import O6Hand
        from src.hand.o6 import O6_JOINT_NAMES

        direct_hand = O6Hand(side=arm, interface_name=args.can)
        try:
            direct_hand.connect()
            initial_feedback = direct_hand.get_angles(timeout_ms=1000)
        except Exception as exc:
            with suppress(Exception):
                direct_hand.disconnect()
            node.destroy_node()
            rclpy.shutdown()
            raise SystemExit(f"O6 did not return valid feedback on {args.can}: {exc}") from exc
        if len(initial_feedback) != 6 or not all(
            math.isfinite(float(value)) and 0.0 <= float(value) <= 100.0
            for value in initial_feedback
        ):
            direct_hand.disconnect()
            node.destroy_node()
            rclpy.shutdown()
            raise SystemExit(f"O6 returned invalid feedback on {args.can}: {initial_feedback}")
        joint_names = list(O6_JOINT_NAMES)

    print(f"[HAND] arm={arm} | f=next preset | q=quit | binary state 0=open 1=closed", flush=True)
    print(
        f"[HAND] backend={args.backend}"
        + (f" | can={args.can} | feedback={[round(value, 1) for value in initial_feedback]}" if direct_hand else "")
        + f" | cycle: {' -> '.join(cycle)} | execute={'yes' if args.execute else 'no'}",
        flush=True,
    )

    def publish_gripper_state() -> None:
        if current_state is None:
            return
        message = UInt8()
        message.data = current_state
        gripper_state_pub.publish(message)

    def publish_joint_state(values: list[float]) -> None:
        if joint_state_pub is None:
            return
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.name = joint_names
        message.position = [float(value) for value in values]
        joint_state_pub.publish(message)

    if direct_hand is not None:
        publish_joint_state(initial_feedback)

    def send_preset(name: str) -> None:
        nonlocal current_state
        preset = presets[name]
        if command_pub is None:
            print(f"\n[HAND DRY-RUN] {name} state={preset['gripper_state']} positions={preset['positions']}", flush=True)
            return
        expected = len(preset["positions"])
        message = JointState()
        message.header.stamp = node.get_clock().now().to_msg()
        message.position = list(preset["positions"])
        message.velocity = [float(config.get("speed", 40.0))] * expected
        message.effort = [float(config.get("force", 40.0))] * expected
        if direct_hand is not None:
            try:
                direct_hand.set_angles(preset["source_positions"])
                command_pub.publish(message)
                feedback = direct_hand.get_angles(timeout_ms=500)
                publish_joint_state(feedback)
            except Exception as exc:
                print(f"\n[HAND] {name} failed: {exc}", flush=True)
                return
            current_state = int(preset["gripper_state"])
            publish_gripper_state()
            print(
                f"\n[HAND] executed {name} state={current_state} "
                f"feedback={[round(value, 1) for value in feedback]}",
                flush=True,
            )
            return
        if not latest_state:
            deadline = time.monotonic() + float(config["state_timeout_s"])
            while time.monotonic() < deadline and rclpy.ok() and latest_state is None:
                rclpy.spin_once(node, timeout_sec=0.05)
        if latest_state is None:
            print(f"\n[HAND] no state received on {state_topic}; command skipped", flush=True)
            return
        # Vendor feedback may contain passive/derived channels (the installed
        # O6 reports 11 state values while accepting 6-value commands).  The
        # command vector is validated against the configured preset; state
        # length is intentionally not required to match it.
        if not latest_state.position:
            print(f"\n[HAND] empty state on {state_topic}; command skipped", flush=True)
            return
        if not any(math.isfinite(float(value)) and float(value) >= 0.0 for value in latest_state.position):
            print(f"\n[HAND] state on {state_topic} contains no valid position; command skipped", flush=True)
            return
        end = time.monotonic() + float(config["hold_seconds"])
        period = 1.0 / float(config["publish_hz"])
        while time.monotonic() < end and rclpy.ok():
            command_pub.publish(message)
            rclpy.spin_once(node, timeout_sec=0.0)
            time.sleep(period)
        current_state = int(preset["gripper_state"])
        publish_gripper_state()
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
                publish_gripper_state()
                if direct_hand is not None:
                    feedback = cached_o6_angles(direct_hand)
                    if feedback is not None:
                        publish_joint_state(feedback)
                next_state = now + state_period
            rclpy.spin_once(node, timeout_sec=0.01)
            import select
            ready, _, _ = select.select([fd], [], [], 0.02)
            if not ready:
                continue
            key = os.read(fd, 1).decode("utf-8", errors="ignore").lower()
            action = classify_hand_key(key)
            if action == "quit":
                break
            if action != "preset":
                continue
            index, name = next_preset(cycle, index)
            send_preset(name)
    finally:
        with suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old_tty)
        if direct_hand is not None:
            with suppress(Exception):
                direct_hand.disconnect()
        node.destroy_node()
        rclpy.shutdown()
    print("\n[HAND] controller exited; no further commands will be sent", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
