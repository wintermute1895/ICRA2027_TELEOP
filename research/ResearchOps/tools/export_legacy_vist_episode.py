#!/usr/bin/env python3
"""Export a legacy VIST ROS2 bag into the current episode JSONL contract.

This adapter is read-only. Its command proxy is the historical filtered
LinkerTA command, not the vendor FollowJoint command. That semantic choice is
recorded in the output manifest and must not be hidden in confirmatory work.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


TOPICS = {
    "state": "/robot1/left_arm/joint_states",
    "master_raw": "/left_arm_joint_control",
    "master_filtered": "/filtered_left_joint_control",
    "rgb": "/camera/color/image_raw",
    "depth": "/camera/depth/image_rect_raw",
}

# Verified against legacy VIST 2026-03 command/state samples. This is a
# historical controller convention, not the current robot command convention.
LEGACY_VIST_LEFT_DEGREE_SIGNS = (1.0, 1.0, 1.0, -1.0, 1.0, -1.0, 1.0)


def stamp_ns(message: Any, fallback: int) -> int:
    stamp = getattr(getattr(message, "header", None), "stamp", None)
    if stamp is None:
        return int(fallback)
    value = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    return value if value > 0 else int(fallback)


def latest_lookup(samples: list[tuple[int, Any]], maximum_age_ns: int):
    samples.sort(key=lambda item: item[0])
    stamps = [item[0] for item in samples]

    def lookup(stamp: int) -> Any | None:
        index = bisect.bisect_right(stamps, stamp) - 1
        if index < 0 or stamp - stamps[index] > maximum_age_ns:
            return None
        return samples[index][1]
    return lookup


def nearest_frame(stamps: list[int], topic: str, state_stamp: int, maximum_age_ns: int) -> dict[str, Any] | None:
    if not stamps:
        return None
    index = bisect.bisect_left(stamps, state_stamp)
    candidates = stamps[max(0, index - 1):index + 1]
    nearest = min(candidates, key=lambda item: abs(item - state_stamp))
    age_ns = abs(nearest - state_stamp)
    if age_ns > maximum_age_ns:
        return None
    return {"topic": topic, "header_stamp_ns": nearest, "age_ms": age_ns / 1e6, "alignment": "nearest_header_stamp"}


def transform_command(message: Any, unit: str, signs: tuple[float, ...]) -> list[float]:
    values = [float(value) for value in message.position]
    if len(values) != len(signs):
        raise SystemExit(f"legacy command has {len(values)} joints; profile expects {len(signs)}")
    scale = math.pi / 180.0 if unit == "degrees" else 1.0
    return [sign * value * scale for sign, value in zip(signs, values)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, required=True, help="legacy episode directory containing one .db3")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--max-age-ms", type=float, default=100.0)
    parser.add_argument("--command-unit", choices=("degrees", "radians"), default="degrees")
    parser.add_argument("--command-sign-profile", choices=("legacy_vist_left", "identity"), default="legacy_vist_left")
    args = parser.parse_args()
    if not args.bag.is_dir():
        raise SystemExit(f"--bag must be the legacy episode directory: {args.bag}")
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(args.bag), storage_id="sqlite3"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    available = {entry.name: entry.type for entry in reader.get_all_topics_and_types()}
    missing = {name: topic for name, topic in TOPICS.items() if topic not in available}
    if "state" in missing:
        raise SystemExit(f"required state topic missing: {TOPICS['state']}")
    requested = {topic: get_message(available[topic]) for topic in TOPICS.values() if topic in available}
    raw: list[tuple[int, Any]] = []
    filtered: list[tuple[int, Any]] = []
    states: list[tuple[int, int, Any]] = []
    frames = {"rgb": [], "depth": []}
    by_topic = {topic: name for name, topic in TOPICS.items()}
    while reader.has_next():
        topic, payload, receipt_stamp = reader.read_next()
        if topic not in requested:
            continue
        message = deserialize_message(payload, requested[topic])
        header_stamp = stamp_ns(message, receipt_stamp)
        name = by_topic[topic]
        if name == "master_raw":
            raw.append((header_stamp, message))
        elif name == "master_filtered":
            filtered.append((header_stamp, message))
        elif name == "state":
            states.append((header_stamp, int(receipt_stamp), message))
        else:
            frames[name].append(header_stamp)
    states.sort(key=lambda item: item[0])
    if not states:
        raise SystemExit("state topic contained no messages")
    for values in frames.values():
        values.sort()
    maximum_age_ns = int(args.max_age_ms * 1e6)
    signs = LEGACY_VIST_LEFT_DEGREE_SIGNS if args.command_sign_profile == "legacy_vist_left" else (1.0,) * len(states[0][2].position)
    raw_for = latest_lookup(raw, maximum_age_ns)
    filtered_for = latest_lookup(filtered, maximum_age_ns)
    episode_id = args.episode_id or args.bag.name
    records = []
    for index, (stamp, receipt, state) in enumerate(states):
        raw_message = raw_for(stamp)
        filtered_message = filtered_for(stamp)
        raw_command = None if raw_message is None else transform_command(raw_message, args.command_unit, signs)
        filtered_command = None if filtered_message is None else transform_command(filtered_message, args.command_unit, signs)
        records.append({
            "schema": "robot_teleop.episode/v1",
            "episode_id": episode_id,
            "source_domain": "real",
            "source_provenance": "legacy_vist",
            "sample_index": index,
            "header_stamp_ns": stamp,
            "receipt_stamp_ns": receipt,
            "clock_source": "ros2_header",
            "arm": "left",
            "joint_names": list(state.name),
            "master_joint_raw": raw_command,
            "master_joint_filtered_rad": filtered_command,
            "mapped_joint_command_rad": filtered_command,
            "robot_joint_state_rad": [float(value) for value in state.position],
            "tcp_pose_base": None,
            "rgb": nearest_frame(frames["rgb"], TOPICS["rgb"], stamp, maximum_age_ns),
            "depth": nearest_frame(frames["depth"], TOPICS["depth"], stamp, maximum_age_ns),
            "camera_info": None,
            "tf": None,
            "data_quality_score": None,
            "success": None,
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    manifest = {
        "schema": "robot_teleop.legacy-episode-export-manifest/v1",
        "source_domain": "real",
        "source_provenance": "legacy_vist",
        "bag": str(args.bag.resolve()),
        "episode_id": episode_id,
        "topic_mapping": {
            "state": TOPICS["state"],
            "master_raw": TOPICS["master_raw"],
            "master_filtered": TOPICS["master_filtered"],
            "mapped_command_proxy": TOPICS["master_filtered"],
            "command_unit_before_transform": args.command_unit,
            "command_sign_profile": args.command_sign_profile,
            "command_signs": signs,
            "rgb": TOPICS["rgb"],
            "depth": TOPICS["depth"],
        },
        "missing_topics": missing,
        "semantic_limitations": [
            "mapped_joint_command_rad is proxied from filtered LinkerTA control, not decoded from legacy FollowJoint.",
            "The selected historical unit/sign profile is a hypothesis verified only for this legacy controller convention.",
            "No legacy success, condition, perturbation, reference revision or safety label is inferred.",
            "Export is eligible for legacy replay only until joint order, units and coordinate semantics are checked.",
        ],
        "sample_count": len(records),
        "hardware_accessed": False,
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "manifest": str(manifest_path), "samples": len(records), "missing": missing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
