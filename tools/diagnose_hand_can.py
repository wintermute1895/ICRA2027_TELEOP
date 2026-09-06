#!/usr/bin/env python3
"""Read-only SocketCAN diagnostic for LinkerHand interfaces.

Never opens an interface, invokes the hand SDK, or transmits a CAN frame.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], timeout_s: float = 3.0) -> dict[str, object]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "output": str(exc)}
    return {"ok": result.returncode == 0, "output": (result.stdout or result.stderr).strip()}


def interface_report(interface: str, listen_s: float) -> dict[str, object]:
    report: dict[str, object] = {"interface": interface}
    report["ip_link"] = run(["ip", "-details", "link", "show", interface])
    sysfs = Path("/sys/class/net") / interface
    report["exists"] = sysfs.is_dir()
    if sysfs.is_dir():
        report["operstate"] = (sysfs / "operstate").read_text(encoding="utf-8").strip()
    if listen_s > 0.0:
        if shutil.which("candump") is None:
            report["candump"] = {"ok": False, "output": "candump is not installed; install can-utils for passive frame observation"}
        else:
            observed = run(["timeout", "--signal=INT", f"{listen_s:g}s", "candump", "-L", interface], timeout_s=listen_s + 2.0)
            observed["expected_timeout"] = True
            # timeout returns 124 after an otherwise healthy passive listen.
            observed["ok"] = "No such device" not in str(observed["output"])
            report["candump"] = observed
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", action="append", default=[], help="SocketCAN interface; repeatable")
    parser.add_argument("--listen-s", type=float, default=0.0, help="passively run candump for this duration")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.listen_s < 0:
        parser.error("--listen-s must be non-negative")
    interfaces = args.interface or ["can0", "can1"]
    report = {
        "schema": "robot_teleop.hand-can-diagnostic/v1",
        "mode": "read_only",
        "transmits_can_frames": False,
        "interfaces": [interface_report(interface, args.listen_s) for interface in interfaces],
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
