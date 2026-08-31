#!/usr/bin/env python3
"""Read-only preflight for the ROS2/Conda teleoperation workspace."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROS_PACKAGES = ("rclcpp", "rclpy", "launch", "launch_ros", "sensor_msgs")


def command(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return result.returncode == 0, (result.stdout or result.stderr).strip()


def ros_topic_has_sample(topic: str, timeout_s: float) -> tuple[bool, str]:
    """Read one ROS message without publishing or changing the graph."""
    try:
        result = subprocess.run(
            ["ros2", "topic", "echo", "--once", topic], text=True,
            capture_output=True, timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"no sample within {timeout_s:g}s: {exc}"
    return result.returncode == 0 and bool(result.stdout.strip()), (result.stdout or result.stderr).strip()[:240]


def capture_topics(source: str, arms: tuple[str, ...], require_tactile: bool) -> tuple[str, ...]:
    robot = "/sim/robot1" if source == "sim" else "/robot1"
    topics: list[str] = []
    for arm in arms:
        topics.extend((
            f"/teleop/{arm}/master_joint_raw", f"/teleop/{arm}/master_joint_filtered",
            f"/teleop/{arm}/mapped_joint_command", f"{robot}/{arm}_arm/joint_states",
        ))
        if source == "real":
            topics.append(f"{robot}/{arm}_arm/vendor_command")
            if require_tactile:
                topics.extend((
                    f"/cb_{arm}_hand_force", f"/cb_{arm}_hand_matrix_touch",
                    f"/cb_{arm}_hand_matrix_touch_mass",
                ))
    return tuple(topics)


def check(mode: str, *, source: str = "real", arms: tuple[str, ...] = ("left", "right"), require_tactile: bool = False, require_samples: bool = False, sample_timeout_s: float = 3.0) -> dict:
    result: dict = {"root": str(ROOT), "python": sys.executable, "platform": platform.platform(), "checks": []}

    def add(name: str, ok: bool, detail: str, required: bool = True) -> None:
        result["checks"].append({"name": name, "ok": ok, "required": required, "detail": detail})

    if mode in ("all", "ros2", "hand"):
        for package in ROS_PACKAGES:
            ok, detail = command(["ros2", "pkg", "prefix", package]) if shutil.which("ros2") else (False, "ros2 not found")
            add(f"ros2:{package}", ok, detail or "available")
    if mode in ("all", "ros2", "hand"):
        python_can_available = importlib.util.find_spec("can") is not None
        add(
            "python:can",
            python_can_available,
            "python-can import is available; required by the LinkerHand SocketCAN SDK"
            if python_can_available else "python-can is missing; install the system package python3-can",
        )
    if mode in ("all", "hand"):
        for package in ("hand_adapter", "linker_hand_ros2_sdk"):
            ok, detail = command(["ros2", "pkg", "prefix", package]) if shutil.which("ros2") else (False, "ros2 not found")
            add(f"hand:{package}", ok, detail or "available")
        for interface in ("can0", "can1"):
            ok, detail = command(["ip", "-details", "link", "show", interface]) if shutil.which("ip") else (False, "ip command not found")
            add(f"hand:{interface}", ok, detail.splitlines()[0] if detail else "not present", required=False)
        for profile in (ROOT / "config/hands/l20lite.yaml", ROOT / "config/hands/o6.yaml"):
            add(f"hand:profile:{profile.stem}", profile.is_file(), str(profile))
    if mode == "capture":
        if not shutil.which("ros2"):
            add("capture:ros2", False, "ros2 not found")
        else:
            listed, detail = command(["ros2", "topic", "list"])
            visible = set(detail.splitlines()) if listed else set()
            for topic in capture_topics(source, arms, require_tactile):
                exists = topic in visible
                add(f"capture:visible:{topic}", exists, "visible" if exists else "topic not present")
                if exists and require_samples:
                    ok, sample_detail = ros_topic_has_sample(topic, sample_timeout_s)
                    add(f"capture:sample:{topic}", ok, sample_detail or "sample received")
            if source == "real" and require_tactile:
                for arm in arms:
                    force = f"/cb_{arm}_hand_force"
                    matrix = f"/cb_{arm}_hand_matrix_touch"
                    mass = f"/cb_{arm}_hand_matrix_touch_mass"
                    force_available = force in visible
                    matrix_available = matrix in visible and mass in visible
                    modality = "force" if force_available else ("matrix" if matrix_available else None)
                    add(
                        f"capture:tactile:{arm}", modality is not None,
                        f"{modality} tactile modality visible" if modality else "need force, or both matrix_touch and matrix_touch_mass",
                    )
                    sample_topics = (force,) if modality == "force" else ((matrix, mass) if modality == "matrix" else ())
                    for topic in sample_topics:
                        if not require_samples:
                            continue
                        ok, sample_detail = ros_topic_has_sample(topic, sample_timeout_s)
                        add(f"capture:tactile-sample:{topic}", ok, sample_detail or "sample received")
    add("urdf:robot_model", False, "no default model: the obsolete O2 z=0 splice was removed; pass an explicitly validated model to simulation tools", required=False)

    interface_source = ROOT / "ros2_ws/src/lbot_arm_interfaces/package.xml"
    add("source:lbot_arm_interfaces", interface_source.is_file(), str(interface_source))

    sdk_candidates = list((ROOT / "third_party/linkerbot_sdk/lib").glob("**/liblbot_api.so*"))
    add("sdk:liblbot_api", bool(sdk_candidates), ", ".join(map(str, sdk_candidates[:3])) or "not found")
    ok, detail = command(["ip", "link", "show", "can0"]) if shutil.which("ip") else (False, "ip command not found")
    add("network:can0", ok, detail.splitlines()[0] if detail else "not present", required=False)
    result["summary"] = {
        "required_pass": sum(c["ok"] for c in result["checks"] if c["required"]),
        "required_total": sum(c["required"] for c in result["checks"]),
        "optional_failures": [c["name"] for c in result["checks"] if not c["ok"] and not c["required"]],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only teleoperation environment preflight")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--mode", choices=("all", "ros2", "hand", "capture"), default="all")
    parser.add_argument("--source", choices=("real", "sim"), default="real", help="capture graph source domain")
    parser.add_argument("--arms", default="left,right", help="comma-separated arms for --mode capture")
    parser.add_argument("--require-tactile", action="store_true", help="require one supported tactile modality for each selected arm")
    parser.add_argument("--require-samples", action="store_true", help="also wait for one message per capture topic; disabled by default so the operator need not move before startup")
    parser.add_argument("--sample-timeout-s", type=float, default=3.0, help="per-topic sample timeout for --mode capture")
    args = parser.parse_args()
    arms = tuple(item.strip() for item in args.arms.split(",") if item.strip())
    if not arms or any(item not in {"left", "right"} for item in arms):
        parser.error("--arms must contain left and/or right")
    if args.sample_timeout_s <= 0:
        parser.error("--sample-timeout-s must be positive")
    result = check(args.mode, source=args.source, arms=arms, require_tactile=args.require_tactile, require_samples=args.require_samples, sample_timeout_s=args.sample_timeout_s)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for item in result["checks"]:
            mark = "PASS" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
            print(f"[{mark}] {item['name']}: {item['detail']}")
        print("Required: {required_pass}/{required_total}".format(**result["summary"]))
    return 0 if result["summary"]["required_pass"] == result["summary"]["required_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
