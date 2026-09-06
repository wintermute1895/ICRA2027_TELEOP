#!/usr/bin/env python3
"""Extract a small timestamped RGB keyframe set from a ROS2 bag.

This is a read-only preprocessing step for offline visual auditing. It keeps
the bag immutable and selects frames using each camera's actual ROS header
timestamps; no common camera FPS is assumed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

from export_rosbag_episode import open_reader, stamp_ns


def decode(message):
    if hasattr(message, "format") and hasattr(message, "data"):
        return cv2.imdecode(np.frombuffer(bytes(message.data), dtype=np.uint8), cv2.IMREAD_COLOR)
    encoding = str(getattr(message, "encoding", ""))
    if encoding not in {"rgb8", "bgr8", "rgba8", "bgra8", "mono8"}:
        raise ValueError(f"unsupported image encoding: {encoding}")
    channels = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4, "mono8": 1}[encoding]
    image = np.frombuffer(bytes(message.data), dtype=np.uint8).reshape(
        int(message.height), int(message.step)
    )[:, : int(message.width) * channels]
    image = image.reshape(int(message.height), int(message.width), channels)
    conversion = {
        "rgb8": cv2.COLOR_RGB2BGR,
        "bgr8": None,
        "rgba8": cv2.COLOR_RGBA2BGR,
        "bgra8": cv2.COLOR_BGRA2BGR,
        "mono8": cv2.COLOR_GRAY2BGR,
    }[encoding]
    return image if conversion is None else cv2.cvtColor(image, conversion)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, required=True)
    parser.add_argument("--topic", action="append", required=True, help="RGB topic; repeatable")
    parser.add_argument("--camera-id", action="append", required=True, help="ID in topic order")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval-s", type=float, default=5.0)
    parser.add_argument("--max-frames-per-camera", type=int, default=8)
    args = parser.parse_args()
    if len(args.topic) != len(args.camera_id):
        raise SystemExit("--topic and --camera-id must be repeated the same number of times")
    if len(set(args.camera_id)) != len(args.camera_id):
        raise SystemExit("--camera-id values must be unique")
    if args.interval_s <= 0 or args.max_frames_per_camera < 1:
        raise SystemExit("--interval-s must be positive and --max-frames-per-camera >= 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reader, temporary, _ = open_reader(args.bag)
    topic_types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    missing = [topic for topic in args.topic if topic not in topic_types]
    if missing:
        raise SystemExit(f"RGB topic(s) missing from bag: {', '.join(missing)}")
    message_types = {topic: get_message(topic_types[topic]) for topic in args.topic}
    next_target: dict[str, int | None] = {topic: None for topic in args.topic}
    rows: list[dict[str, object]] = []
    counts = {topic: 0 for topic in args.topic}
    frame_root = args.output_dir / "frames"
    try:
        while reader.has_next():
            topic, raw, bag_time_ns = reader.read_next()
            if topic not in message_types or counts[topic] >= args.max_frames_per_camera:
                continue
            message = deserialize_message(raw, message_types[topic])
            timestamp_ns = stamp_ns(message, bag_time_ns)
            target = next_target[topic]
            if target is not None and timestamp_ns < target:
                continue
            image = decode(message)
            if image is None or image.size == 0:
                continue
            camera_id = args.camera_id[args.topic.index(topic)]
            camera_dir = frame_root / camera_id
            camera_dir.mkdir(parents=True, exist_ok=True)
            path = camera_dir / f"{timestamp_ns}.png"
            if not cv2.imwrite(str(path), image):
                raise SystemExit(f"failed to write {path}")
            rows.append(
                {
                    "schema": "robot_teleop.vlm-keyframe/v0.1",
                    "timestamp_ns": int(timestamp_ns),
                    "camera_id": camera_id,
                    "topic": topic,
                    "reference": str(path.resolve()),
                }
            )
            counts[topic] += 1
            next_target[topic] = timestamp_ns + int(args.interval_s * 1_000_000_000)
    finally:
        if temporary is not None:
            temporary.cleanup()
    if not rows:
        raise SystemExit("no RGB keyframes extracted")
    rows.sort(key=lambda row: (int(row["timestamp_ns"]), str(row["camera_id"])))
    index = args.output_dir / "keyframes.jsonl"
    index.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"index": str(index), "rows": len(rows), "counts": {args.camera_id[i]: counts[t] for i, t in enumerate(args.topic)}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
