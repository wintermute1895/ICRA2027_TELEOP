#!/usr/bin/env python3
"""Measure ROS message timestamp age, jitter, drops, and cross-topic skew.

Read-only diagnostic. It subscribes to topics but never connects to the robot
and never publishes commands. Use the system ROS2 Python, not a Conda Python.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

# ROS2 Humble on this machine is built for system Python 3.10.  If the user
# launches this script from Conda base (Python 3.12), re-exec with the system
# interpreter before importing rclpy.  This keeps the command ergonomic while
# preserving the ROS2/Conda separation used by the rest of the project.
if sys.version_info[:2] != (3, 10) and Path("/usr/bin/python3").is_file():
    os.environ.pop("PYTHONHOME", None)
    os.execv("/usr/bin/python3", ["/usr/bin/python3", *sys.argv])

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image, JointState
from tf2_msgs.msg import TFMessage


TOPIC_TYPES = {
    "joint": JointState,
    "image": Image,
    "camera_info": CameraInfo,
    "tf": TFMessage,
}


def stamp_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


class TimingProbe(Node):
    def __init__(self, topics: list[tuple[str, str]]) -> None:
        super().__init__("vist_time_sync_probe")
        self.samples: dict[str, list[dict[str, int]]] = {name: [] for name, _ in topics}
        for name, kind in topics:
            message_type = TOPIC_TYPES[kind]
            self.create_subscription(
                message_type,
                name,
                lambda msg, selected=name, selected_kind=kind: self._on_message(
                    selected, selected_kind, msg
                ),
                50,
            )

    def _on_message(self, name: str, kind: str, msg) -> None:
        receipt_ros = int(self.get_clock().now().nanoseconds)
        receipt_wall = time.time_ns()
        if kind == "tf":
            stamps = [stamp_ns(item.header.stamp) for item in msg.transforms]
        else:
            stamps = [stamp_ns(msg.header.stamp)]
        for header in stamps:
            if header <= 0:
                continue
            self.samples[name].append(
                {
                    "header_ns": header,
                    "receipt_ros_ns": receipt_ros,
                    "receipt_wall_ns": receipt_wall,
                }
            )


def topic_report(samples: list[dict[str, int]]) -> dict[str, object]:
    if not samples:
        return {"count": 0, "status": "missing"}
    headers = [item["header_ns"] for item in samples]
    receipt = [item["receipt_ros_ns"] for item in samples]
    ages_ms = [(r - h) / 1e6 for r, h in zip(receipt, headers)]
    periods_ms = [(b - a) / 1e6 for a, b in zip(headers, headers[1:]) if b > a]
    result: dict[str, object] = {
        "count": len(samples),
        "status": "ok",
        "first_header_ns": headers[0],
        "last_header_ns": headers[-1],
        "header_duration_s": max(0.0, (headers[-1] - headers[0]) / 1e9),
        "header_age_ms": {
            "median": statistics.median(ages_ms),
            "p95": percentile(ages_ms, 95),
            "max": max(ages_ms),
        },
        "header_period_ms": {
            "median": statistics.median(periods_ms) if periods_ms else None,
            "jitter_mad_ms": median_absolute_deviation(periods_ms) if periods_ms else None,
        },
    }
    return result


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = (len(values) - 1) * p / 100.0
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median([abs(value - center) for value in values])


def nearest_skew_ms(first: list[dict[str, int]], second: list[dict[str, int]]) -> dict[str, object]:
    if not first or not second:
        return {"count": 0, "status": "missing"}
    right = sorted(item["header_ns"] for item in second)
    differences = []
    for item in first:
        value = item["header_ns"]
        nearest = min(right, key=lambda candidate: abs(candidate - value))
        differences.append(abs(nearest - value) / 1e6)
    return {
        "count": len(differences),
        "status": "ok",
        "median_abs_skew_ms": statistics.median(differences),
        "p95_abs_skew_ms": percentile(differences, 95),
        "max_abs_skew_ms": max(differences),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=10.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--camera-namespace", default="/camera/camera")
    args = parser.parse_args()
    if args.duration_s <= 0:
        raise SystemExit("--duration-s must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("ROS_LOG_DIR", str(args.output.parent / "ros_logs"))
    camera = args.camera_namespace.rstrip("/")
    topics = [
        ("/left_arm_joint_control", "joint"),
        ("/right_arm_joint_control", "joint"),
        ("/teleop/left/master_joint_raw", "joint"),
        ("/teleop/left/master_joint_filtered", "joint"),
        ("/teleop/left/mapped_joint_command", "joint"),
        ("/teleop/right/master_joint_raw", "joint"),
        ("/teleop/right/master_joint_filtered", "joint"),
        ("/teleop/right/mapped_joint_command", "joint"),
        ("/robot1/left_arm/joint_states", "joint"),
        ("/robot1/right_arm/joint_states", "joint"),
        (f"{camera}/color/image_raw", "image"),
        (f"{camera}/aligned_depth_to_color/image_raw", "image"),
        (f"{camera}/color/camera_info", "camera_info"),
        (f"{camera}/depth/camera_info", "camera_info"),
    ]
    rclpy.init()
    probe = TimingProbe(topics)
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.duration_s:
            rclpy.spin_once(probe, timeout_sec=0.1)
    finally:
        probe.destroy_node()
        rclpy.shutdown()

    report = {
        "schema": "robot_teleop.time-sync-report/v1",
        "created_at_unix_ns": time.time_ns(),
        "duration_s": args.duration_s,
        "clock_policy": {
            "comparison_clock": "ROS2 message header.stamp",
            "receipt_clock": "node ROS clock plus wall clock diagnostic",
            "hardware_sync_claim": False,
            "note": "This report measures ROS timestamp consistency; hardware trigger/PTP must be declared separately.",
        },
        "topics": {name: topic_report(probe.samples[name]) for name, _ in topics},
        "cross_topic_skew": {
            "color_vs_depth": nearest_skew_ms(
                probe.samples[f"{camera}/color/image_raw"],
                probe.samples[f"{camera}/aligned_depth_to_color/image_raw"],
            ),
            "left_source_vs_filtered": nearest_skew_ms(
                probe.samples["/left_arm_joint_control"],
                probe.samples["/teleop/left/master_joint_filtered"],
            ),
            "right_source_vs_filtered": nearest_skew_ms(
                probe.samples["/right_arm_joint_control"],
                probe.samples["/teleop/right/master_joint_filtered"],
            ),
            "control_left_vs_robot_left": nearest_skew_ms(
                probe.samples["/left_arm_joint_control"],
                probe.samples["/robot1/left_arm/joint_states"],
            ),
            "control_right_vs_robot_right": nearest_skew_ms(
                probe.samples["/right_arm_joint_control"],
                probe.samples["/robot1/right_arm/joint_states"],
            ),
            "color_vs_robot_left": nearest_skew_ms(
                probe.samples[f"{camera}/color/image_raw"],
                probe.samples["/robot1/left_arm/joint_states"],
            ),
            "color_vs_robot_right": nearest_skew_ms(
                probe.samples[f"{camera}/color/image_raw"],
                probe.samples["/robot1/right_arm/joint_states"],
            ),
            "depth_vs_robot_left": nearest_skew_ms(
                probe.samples[f"{camera}/aligned_depth_to_color/image_raw"],
                probe.samples["/robot1/left_arm/joint_states"],
            ),
            "depth_vs_robot_right": nearest_skew_ms(
                probe.samples[f"{camera}/aligned_depth_to_color/image_raw"],
                probe.samples["/robot1/right_arm/joint_states"],
            ),
        },
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
