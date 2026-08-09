#!/usr/bin/env python3
"""Read-only preflight for the ROS2/Conda teleoperation workspace."""
from __future__ import annotations

import argparse
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


def check(mode: str) -> dict:
    result: dict = {"root": str(ROOT), "python": sys.executable, "platform": platform.platform(), "checks": []}

    def add(name: str, ok: bool, detail: str, required: bool = True) -> None:
        result["checks"].append({"name": name, "ok": ok, "required": required, "detail": detail})

    if mode in ("all", "ros2"):
        for package in ROS_PACKAGES:
            ok, detail = command(["ros2", "pkg", "prefix", package]) if shutil.which("ros2") else (False, "ros2 not found")
            add(f"ros2:{package}", ok, detail or "available")
    urdf = ROOT / "IROS_teleop/config/combined_robot/robot.urdf"
    add("urdf:combined_robot", urdf.is_file(), str(urdf))
    try:
        root = ET.parse(urdf).getroot()
        joints = [j for j in root.findall("joint") if j.get("type") != "fixed"]
        add("urdf:parse", True, f"{len(joints)} movable joints")
    except (OSError, ET.ParseError) as exc:
        add("urdf:parse", False, str(exc))

    interface_source = ROOT / "arm_teleop/src/lbot_arm_interfaces/package.xml"
    add("source:lbot_arm_interfaces", interface_source.is_file(), str(interface_source))

    sdk_candidates = list((ROOT / "arm_teleop/src/lbot_driver/lib").glob("**/liblbot_api.so*"))
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
    parser.add_argument("--mode", choices=("all", "ros2"), default="all")
    args = parser.parse_args()
    result = check(args.mode)
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
