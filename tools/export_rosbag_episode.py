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
    parser.add_argument("--extra-camera-namespace", action="append", default=[], help="additional camera namespace; repeatable")
    parser.add_argument("--camera-id", action="append", default=[], help="camera id(s), in namespace order")
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
    camera_namespaces = [camera_ns] + [item.rstrip("/") for item in opt.extra_camera_namespace]
    camera_ids = list(opt.camera_id) or ["external_rgb"] + [f"camera_{index}" for index in range(1, len(camera_namespaces))]
    if len(camera_ids) != len(camera_namespaces):
        raise SystemExit("--camera-id count must match camera namespaces")
    teleop_ns = opt.teleop_namespace.rstrip("/")
    state_topic = f"{robot_ns}/{opt.arm}_arm/joint_states"
    master_raw_topic = f"{teleop_ns}/{opt.arm}/master_joint_raw"
    master_filtered_topic = f"{teleop_ns}/{opt.arm}/master_joint_filtered"
    command_topic = f"{teleop_ns}/{opt.arm}/mapped_joint_command"
    vendor_command_topic = f"{robot_ns}/{opt.arm}_arm/vendor_command"
    tcp_pose_topic = f"{robot_ns}/{opt.arm}_arm/pose_states"
    rgb_topic = f"{camera_ns}/color/image_raw"
    depth_topic = f"{camera_ns}/aligned_depth_to_color/image_raw"
    camera_topics = [(camera_id, namespace, f"{namespace}/color/image_raw", f"{namespace}/aligned_depth_to_color/image_raw") for camera_id, namespace in zip(camera_ids, camera_namespaces)]
    tactile_force_topic = f"/cb_{opt.arm}_hand_force"
    tactile_matrix_topic = f"/cb_{opt.arm}_hand_matrix_touch"
    tactile_mass_topic = f"/cb_{opt.arm}_hand_matrix_touch_mass"
    task_context_topic = f"{teleop_ns}/{opt.arm}/task_context"
    sim_context_topic = f"{robot_ns}/{opt.arm}_arm/filter_context"
    reader, temporary, compression_mode = open_reader(opt.bag)
    types = {item.name: get_message(item.type) for item in reader.get_all_topics_and_types()}
    required = (state_topic, master_raw_topic, master_filtered_topic, command_topic, vendor_command_topic, tcp_pose_topic, rgb_topic, depth_topic)
    missing = [topic for topic in required if topic not in types]
    if state_topic not in types:
        raise SystemExit(f"required state topic missing: {state_topic}")
    master_raw: list[tuple[int, Any]] = []
    master_filtered: list[tuple[int, Any]] = []
    commands: list[tuple[int, Any]] = []
    vendor_commands: list[tuple[int, Any]] = []
    tcp_poses: list[tuple[int, Any]] = []
    rgb_stamps: dict[str, list[int]] = {camera_id: [] for camera_id in camera_ids}
    depth_stamps: dict[str, list[int]] = {camera_id: [] for camera_id in camera_ids}
    tactile_force: list[tuple[int, Any]] = []
    tactile_matrix: list[tuple[int, Any]] = []
    tactile_mass: list[tuple[int, Any]] = []
    task_context: list[tuple[int, Any]] = []
    state_samples: list[tuple[int, int, Any]] = []
    max_age_ns = int(opt.max_camera_age_ms * 1e6)
    max_command_age_ns = int(opt.max_command_age_ms * 1e6)
    while reader.has_next():
        topic, raw, bag_time_ns = reader.read_next()
        camera_topic_names = {value for _, _, value, _ in camera_topics} | {value for _, _, _, value in camera_topics}
        if topic not in {state_topic, master_raw_topic, master_filtered_topic, command_topic, vendor_command_topic, tcp_pose_topic, tactile_force_topic, tactile_matrix_topic, tactile_mass_topic, task_context_topic, sim_context_topic} | camera_topic_names:
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
        if topic == vendor_command_topic:
            vendor_commands.append((message_stamp_ns, message))
            continue
        if topic == tcp_pose_topic:
            tcp_poses.append((message_stamp_ns, message))
            continue
        camera_match = next((item for item in camera_topics if topic in {item[2], item[3]}), None)
        if camera_match is not None:
            camera_id = camera_match[0]
            (rgb_stamps if topic == camera_match[2] else depth_stamps)[camera_id].append(message_stamp_ns)
            continue
        if topic == tactile_force_topic:
            tactile_force.append((message_stamp_ns, message))
            continue
        if topic == tactile_matrix_topic:
            tactile_matrix.append((message_stamp_ns, message))
            continue
        if topic == tactile_mass_topic:
            tactile_mass.append((message_stamp_ns, message))
            continue
        if topic in {task_context_topic, sim_context_topic}:
            task_context.append((message_stamp_ns, message))
            continue
        state_samples.append((message_stamp_ns, int(bag_time_ns), message))

    for stamps in (*rgb_stamps.values(), *depth_stamps.values()):
        stamps.sort()
    state_samples.sort(key=lambda item: item[0])

    def tactile_ref(samples: list[tuple[int, Any]], topic_name: str, state_stamp_ns: int) -> dict[str, Any] | None:
        if not samples:
            return None
        stamps = [item[0] for item in samples]
        index = bisect.bisect_right(stamps, state_stamp_ns) - 1
        if index < 0 or state_stamp_ns - stamps[index] > max_command_age_ns:
            return None
        message = samples[index][1]
        value: Any = getattr(message, "data", None)
        if isinstance(value, (tuple, list)):
            value = [float(item) for item in value]
        elif isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = None
        return {"topic": topic_name, "header_stamp_ns": stamps[index], "age_ms": (state_stamp_ns - stamps[index]) / 1e6, "alignment": "latest_header_or_bag_stamp_not_after_state", "value": value}

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
    vendor_for = make_command_lookup(vendor_commands)
    pose_for = make_command_lookup(tcp_poses)
    context_for = make_command_lookup(task_context)

    def context_value(message: Any) -> dict[str, Any] | None:
        if message is None:
            return None
        data = getattr(message, "data", None)
        if isinstance(data, str):
            try:
                value = json.loads(data)
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
        names = getattr(message, "name", None)
        positions = getattr(message, "position", None)
        if isinstance(names, (list, tuple)) and isinstance(positions, (list, tuple)):
            return {str(name): float(value) for name, value in zip(names, positions)}
        return None

    records: list[dict[str, Any]] = []
    for message_stamp_ns, bag_time_ns, message in state_samples:
        command = command_for(message_stamp_ns)
        raw = raw_for(message_stamp_ns)
        filtered = filtered_for(message_stamp_ns)
        vendor = vendor_for(message_stamp_ns)
        pose = pose_for(message_stamp_ns)
        context = context_for(message_stamp_ns)
        tcp_pose = None
        tcp_frame = None
        if pose is not None:
            tcp_frame = getattr(getattr(pose, "header", None), "frame_id", None)
            pose_value = getattr(pose, "pose", None)
            if pose_value is not None:
                tcp_pose = [
                    float(pose_value.position.x), float(pose_value.position.y), float(pose_value.position.z),
                    float(pose_value.orientation.x), float(pose_value.orientation.y),
                    float(pose_value.orientation.z), float(pose_value.orientation.w),
                ]
        controller_command = None
        controller_source = None
        if vendor is not None:
            controller_command = [float(value) for value in getattr(vendor, "joints_rad", [])]
            controller_source = getattr(vendor, "source", None)
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
            "controller_command_rad": controller_command,
            "controller_command_source": controller_source,
            "tcp_pose_base": tcp_pose,
            "tcp_pose_frame": tcp_frame,
            "task_context": context_value(context),
            "rgb": camera_ref(rgb_stamps[camera_ids[0]], rgb_topic, message_stamp_ns),
            "depth": camera_ref(depth_stamps[camera_ids[0]], depth_topic, message_stamp_ns),
            "cameras": {camera_id: {"rgb": camera_ref(rgb_stamps[camera_id], rgb_topic_name, message_stamp_ns), "depth": camera_ref(depth_stamps[camera_id], depth_topic_name, message_stamp_ns)} for camera_id, _, rgb_topic_name, depth_topic_name in camera_topics},
            "tactile_force": tactile_ref(tactile_force, tactile_force_topic, message_stamp_ns),
            "tactile_matrix": tactile_ref(tactile_matrix, tactile_matrix_topic, message_stamp_ns),
            "tactile_mass": tactile_ref(tactile_mass, tactile_mass_topic, message_stamp_ns),
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
            "vendor_command": vendor_command_topic,
            "tcp_pose": tcp_pose_topic,
            "rgb": rgb_topic,
            "depth": depth_topic,
            "tactile_force": tactile_force_topic,
            "tactile_matrix": tactile_matrix_topic,
            "tactile_mass": tactile_mass_topic,
            "task_context": task_context_topic if task_context_topic in types else sim_context_topic,
            "cameras": {camera_id: {"rgb": rgb_topic_name, "depth": depth_topic_name} for camera_id, _, rgb_topic_name, depth_topic_name in camera_topics},
        },
        "missing_topics": missing,
        "camera_alignment": {"policy": "nearest_header_stamp", "maximum_age_ms": opt.max_camera_age_ms},
        "command_alignment": {"policy": "latest_header_stamp_not_after_state", "maximum_age_ms": opt.max_command_age_ms},
        "compression_handling": compression_mode,
        "tactile_alignment": {"policy": "latest_header_or_bag_stamp_not_after_state", "maximum_age_ms": opt.max_command_age_ms},
        "tactile_topics_available": {"force": tactile_force_topic in types, "matrix": tactile_matrix_topic in types, "mass": tactile_mass_topic in types},
        "task_context_topic_available": task_context_topic in types or sim_context_topic in types,
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
