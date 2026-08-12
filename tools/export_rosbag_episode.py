#!/usr/bin/python3
"""Export one arm from a ROS2 bag to the canonical episode JSONL schema.

Read-only: this tool never creates ROS nodes, calls SDKs, or publishes topics.
Simulation and real bags differ only by the configurable state/camera namespaces.
"""
from __future__ import annotations

import argparse
import bisect
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def stamp_ns(message: Any, fallback: int) -> int:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return fallback
    value = int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    return value if value > 0 else fallback


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", type=Path, required=True, help="rosbag2 directory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=("left", "right"), required=True)
    parser.add_argument("--source-domain", choices=("real", "sim"), required=True)
    parser.add_argument("--robot-namespace", default=None)
    parser.add_argument("--camera-namespace", default=None)
    parser.add_argument(
        "--teleop-namespace",
        default="/teleop",
        help="mapped-command namespace; use /vist for historical bags",
    )
    parser.add_argument("--max-camera-age-ms", type=float, default=100.0)
    parser.add_argument("--max-command-age-ms", type=float, default=100.0)
    parser.add_argument("--episode-id", default=None)
    return parser.parse_args()


def open_reader(bag: Path) -> tuple[rosbag2_py.SequentialReader, tempfile.TemporaryDirectory[str] | None, str]:
    """Open a sqlite rosbag, expanding file-level zstd bags into a temporary copy."""
    compressed_files = sorted(bag.glob("*.db3.zstd"))
    temporary: tempfile.TemporaryDirectory[str] | None = None
    input_uri = bag
    compression_mode = "none"
    if compressed_files:
        if len(compressed_files) != 1:
            raise SystemExit(f"only single-file zstd bags are supported: {bag}")
        zstd = shutil.which("zstd")
        if zstd is None:
            raise SystemExit("zstd CLI is required to read a .db3.zstd bag")
        temporary = tempfile.TemporaryDirectory(prefix="rosbag_episode_")
        input_uri = Path(temporary.name) / compressed_files[0].with_suffix("").name
        with input_uri.open("wb") as destination:
            subprocess.run(
                [zstd, "--decompress", "--stdout", str(compressed_files[0])],
                check=True,
                stdout=destination,
            )
        compression_mode = "file-zstd-expanded-to-temporary-copy"
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(input_uri), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    return reader, temporary, compression_mode


def main() -> int:
    opt = args()
    robot_ns = (opt.robot_namespace or ("/sim/robot1" if opt.source_domain == "sim" else "/robot1")).rstrip("/")
    camera_ns = (opt.camera_namespace or ("/sim/camera/camera" if opt.source_domain == "sim" else "/camera/camera")).rstrip("/")
    teleop_ns = opt.teleop_namespace.rstrip("/")
    state_topic = f"{robot_ns}/{opt.arm}_arm/joint_states"
    master_raw_topic = f"{teleop_ns}/{opt.arm}/master_joint_raw"
    master_filtered_topic = f"{teleop_ns}/{opt.arm}/master_joint_filtered"
    command_topic = f"{teleop_ns}/{opt.arm}/mapped_joint_command"
    rgb_topic = f"{camera_ns}/color/image_raw"
    depth_topic = f"{camera_ns}/aligned_depth_to_color/image_raw"
    reader, temporary, compression_mode = open_reader(opt.bag)
    types = {item.name: get_message(item.type) for item in reader.get_all_topics_and_types()}
    required = (state_topic, master_raw_topic, master_filtered_topic, command_topic, rgb_topic, depth_topic)
    missing = [topic for topic in required if topic not in types]
    if state_topic not in types:
        raise SystemExit(f"required state topic missing: {state_topic}")
    master_raw: list[tuple[int, Any]] = []
    master_filtered: list[tuple[int, Any]] = []
    commands: list[tuple[int, Any]] = []
    rgb_stamps: list[int] = []
    depth_stamps: list[int] = []
    state_samples: list[tuple[int, int, Any]] = []
    max_age_ns = int(opt.max_camera_age_ms * 1e6)
    max_command_age_ns = int(opt.max_command_age_ms * 1e6)
    while reader.has_next():
        topic, raw, bag_time_ns = reader.read_next()
        if topic not in {state_topic, master_raw_topic, master_filtered_topic, command_topic, rgb_topic, depth_topic}:
            continue
        message = deserialize_message(raw, types[topic])
        message_stamp_ns = stamp_ns(message, bag_time_ns)
        if topic == master_raw_topic:
            master_raw.append((message_stamp_ns, message))
            continue
        if topic == master_filtered_topic:
            master_filtered.append((message_stamp_ns, message))
            continue
        if topic == command_topic:
            commands.append((message_stamp_ns, message))
            continue
        if topic == rgb_topic:
            rgb_stamps.append(message_stamp_ns)
            continue
        if topic == depth_topic:
            depth_stamps.append(message_stamp_ns)
            continue
        state_samples.append((message_stamp_ns, int(bag_time_ns), message))

    rgb_stamps.sort()
    depth_stamps.sort()
    state_samples.sort(key=lambda item: item[0])

    def camera_ref(stamps: list[int], topic_name: str, state_stamp_ns: int) -> dict[str, Any] | None:
        if not stamps:
            return None
        index = bisect.bisect_left(stamps, state_stamp_ns)
        candidates = stamps[max(0, index - 1):index + 1]
        frame_stamp = min(candidates, key=lambda value: abs(value - state_stamp_ns))
        if abs(state_stamp_ns - frame_stamp) > max_age_ns:
            return None
        return {
            "topic": topic_name,
            "header_stamp_ns": frame_stamp,
            "age_ms": abs(state_stamp_ns - frame_stamp) / 1e6,
            "alignment": "nearest_header_stamp",
        }

    def make_command_lookup(samples: list[tuple[int, Any]]):
        samples.sort(key=lambda item: item[0])
        stamps = [item[0] for item in samples]

        def lookup(state_stamp_ns: int) -> Any | None:
            index = bisect.bisect_right(stamps, state_stamp_ns) - 1
            if index < 0 or state_stamp_ns - stamps[index] > max_command_age_ns:
                return None
            return samples[index][1]

        return lookup

    raw_for = make_command_lookup(master_raw)
    filtered_for = make_command_lookup(master_filtered)
    command_for = make_command_lookup(commands)

    records: list[dict[str, Any]] = []
    for message_stamp_ns, bag_time_ns, message in state_samples:
        command = command_for(message_stamp_ns)
        raw = raw_for(message_stamp_ns)
        filtered = filtered_for(message_stamp_ns)
        records.append({
            "schema": "robot_teleop.episode/v1",
            "episode_id": opt.episode_id or (opt.bag.parent.parent.name if opt.bag.name == "rosbag2" else opt.bag.name),
            "source_domain": opt.source_domain,
            "sample_index": len(records),
            "header_stamp_ns": message_stamp_ns,
            "receipt_stamp_ns": int(bag_time_ns),
            "clock_source": "ros2_header",
            "arm": opt.arm,
            "joint_names": list(message.name),
            "master_joint_raw": None if raw is None else [float(value) for value in raw.position],
            "master_joint_filtered_rad": None if filtered is None else [float(value) for value in filtered.position],
            "robot_joint_state_rad": [float(value) for value in message.position],
            "mapped_joint_command_rad": None if command is None else [float(value) for value in command.position],
            "tcp_pose_base": None,
            "rgb": camera_ref(rgb_stamps, rgb_topic, message_stamp_ns),
            "depth": camera_ref(depth_stamps, depth_topic, message_stamp_ns),
            "camera_info": None,
            "tf": None,
            "data_quality_score": None,
            "success": None,
        })
    if not records:
        raise SystemExit(f"no state records found on {state_topic}")
    opt.output.parent.mkdir(parents=True, exist_ok=True)
    with opt.output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    manifest = {
        "schema": "robot_teleop.episode-export-manifest/v1",
        "source_domain": opt.source_domain,
        "bag": str(opt.bag.resolve()),
        "arm": opt.arm,
        "topics": {
            "state": state_topic,
            "master_raw": master_raw_topic,
            "master_filtered": master_filtered_topic,
            "command": command_topic,
            "rgb": rgb_topic,
            "depth": depth_topic,
        },
        "missing_topics": missing,
        "camera_alignment": {"policy": "nearest_header_stamp", "maximum_age_ms": opt.max_camera_age_ms},
        "command_alignment": {"policy": "latest_header_stamp_not_after_state", "maximum_age_ms": opt.max_command_age_ms},
        "compression_handling": compression_mode,
        "sample_count": len(records),
        "hardware_accessed": False,
    }
    manifest_path = opt.output.with_suffix(opt.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if temporary is not None:
        temporary.cleanup()
    print(json.dumps({"output": str(opt.output), "manifest": str(manifest_path), "samples": len(records), "missing_topics": missing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
