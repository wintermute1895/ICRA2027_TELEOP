#!/usr/bin/env python3
"""Decode one ROS2 Image/CompressedImage topic into timestamped PNG frames.

The rosbag remains immutable.  The emitted JSONL index is an explicit derived
artifact suitable for `canonical_episode_to_act_dataset.py --camera-index`.
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
    image = np.frombuffer(bytes(message.data), dtype=np.uint8).reshape(int(message.height), int(message.step))[:, :int(message.width) * channels]
    image = image.reshape(int(message.height), int(message.width), channels)
    conversion = {"rgb8": cv2.COLOR_RGB2BGR, "bgr8": None, "rgba8": cv2.COLOR_RGBA2BGR, "bgra8": cv2.COLOR_BGRA2BGR, "mono8": cv2.COLOR_GRAY2BGR}[encoding]
    return image if conversion is None else cv2.cvtColor(image, conversion)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--camera-id", default="rgb")
    args = parser.parse_args()
    reader, temporary, _ = open_reader(args.bag)
    types = {item.name: get_message(item.type) for item in reader.get_all_topics_and_types()}
    if args.topic not in types:
        raise SystemExit(f"camera topic missing from bag: {args.topic}")
    frames = args.output_dir / args.camera_id
    frames.mkdir(parents=True, exist_ok=True)
    rows = []
    while reader.has_next():
        topic, raw, bag_stamp = reader.read_next()
        if topic != args.topic:
            continue
        message = deserialize_message(raw, types[topic])
        timestamp = stamp_ns(message, bag_stamp)
        try:
            image = decode(message)
        except ValueError as error:
            raise SystemExit(f"cannot decode {args.topic} at {timestamp}: {error}") from error
        path = frames / f"{timestamp}.png"
        if not cv2.imwrite(str(path), image):
            raise SystemExit(f"failed to write {path}")
        rows.append({"timestamp_ns": timestamp, "camera_id": args.camera_id, "reference": {"frame_reference": str(path.resolve()), "encoding": "png", "width": int(image.shape[1]), "height": int(image.shape[0]), "valid": True}})
    if temporary is not None:
        temporary.cleanup()
    if not rows:
        raise SystemExit(f"no frames decoded from {args.topic}")
    index = args.output_dir / f"{args.camera_id}_frames.jsonl"
    index.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"index": str(index), "frames": len(rows), "camera_id": args.camera_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
