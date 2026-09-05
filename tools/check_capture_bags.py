#!/usr/bin/env python3
"""Read-only integrity check for captured rosbag2 episodes.

Checks the presence and approximate message rate of both RGB cameras, depth,
and the right-arm joint state stream from each episode's metadata.yaml.
It never opens the compressed database and never writes into evidence dirs.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml


REQUIRED_TOPICS = {
    "camera1_rgb": "/camera/camera/color/image_raw",
    "camera2_rgb": "/camera2/camera/color/image_raw",
    "camera1_depth": "/camera/camera/aligned_depth_to_color/image_raw",
    "camera2_depth": "/camera2/camera/aligned_depth_to_color/image_raw",
    "joint_states": "/robot1/right_arm/joint_states",
    "vendor_command": "/robot1/right_arm/vendor_command",
}
EXPECTED_HZ = {
    "camera1_rgb": 15.0,
    "camera2_rgb": 15.0,
    "camera1_depth": 15.0,
    "camera2_depth": 15.0,
    "joint_states": 50.0,
    "vendor_command": 50.0,
}
MIN_RATE_FRACTION = 0.60


def rate_ok(name: str, count: int, duration_s: float) -> tuple[float, bool]:
    expected = EXPECTED_HZ.get(name)
    if expected is None or duration_s <= 0:
        return 0.0, True
    actual = count / duration_s
    return actual, actual >= expected * MIN_RATE_FRACTION


def check_run(run_dir: pathlib.Path) -> dict[str, object]:
    bag_dir = run_dir / "artifacts" / "rosbag2"
    metadata_path = bag_dir / "metadata.yaml"
    issues: list[str] = []
    counts: dict[str, int] = {name: 0 for name in REQUIRED_TOPICS}
    duration_s = 0.0
    if not bag_dir.is_dir():
        issues.append("rosbag2 directory missing")
    elif not metadata_path.is_file():
        issues.append("metadata.yaml missing")
    else:
        try:
            data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
            info = data.get("rosbag2_bagfile_information", {})
            duration_s = float(info.get("duration", {}).get("nanoseconds", 0)) / 1e9
            for entry in info.get("topics_with_message_count", []):
                topic = entry.get("topic_metadata", {}).get("name")
                for name, full_name in REQUIRED_TOPICS.items():
                    if topic == full_name:
                        counts[name] = int(entry.get("message_count", 0))
        except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
            issues.append(f"metadata parse failed: {exc}")

    actual_hz: dict[str, float] = {}
    for name, count in counts.items():
        actual, ok = rate_ok(name, count, duration_s)
        actual_hz[name] = round(actual, 1)
        if count == 0:
            issues.append(f"{name} has no messages")
        elif not ok:
            issues.append(f"{name} rate low: {count}/{duration_s:.1f}s = {actual:.1f}Hz")
    return {
        "episode": run_dir.name,
        "duration_s": round(duration_s, 1),
        "counts": counts,
        "actual_hz": actual_hz,
        "issues": issues,
        "passed": not issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=pathlib.Path, help="data root containing episode directories")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print(f"[FATAL] data root not found: {args.root}", file=sys.stderr)
        return 2
    runs = sorted(
        child for child in args.root.iterdir()
        if child.is_dir() and (child / "run.json").is_file()
    )
    if not runs:
        print(f"[FATAL] no episode directories under {args.root}", file=sys.stderr)
        return 2
    results = [check_run(run) for run in runs]
    failed = [result for result in results if not result["passed"]]
    print(json.dumps(
        {
            "schema": "robot_teleop.capture-bag-integrity/v0.1",
            "data_root": str(args.root),
            "episodes_checked": len(results),
            "episodes_failed": len(failed),
            "results": results,
            "failed_episodes": [result["episode"] for result in failed],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
