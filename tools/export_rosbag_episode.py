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


def deduplicate_state_samples(samples: list[tuple[int, int, Any]]) -> tuple[list[tuple[int, int, Any]], int]:
    """Sort by message time and retain the latest-received sample per timestamp."""
    ordered = sorted(samples, key=lambda item: (item[0], item[1]))
    unique: list[tuple[int, int, Any]] = []
    for sample in ordered:
        if unique and sample[0] == unique[-1][0]:
            unique[-1] = sample
        else:
            unique.append(sample)
    return unique, len(ordered) - len(unique)


def merge_audit_events(events: list[dict[str, Any]], sidecar: Path | None) -> list[dict[str, Any]]:
    combined = list(events)
    if sidecar is not None and sidecar.is_file():
        for line in sidecar.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    combined.append(value)
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for event in combined:
        identity = (
            event.get("episode_id"), event.get("auditor_id"), event.get("sequence"),
            event.get("timestamp_ns"), event.get("event_type"),
        )
        unique[identity] = event
    return sorted(unique.values(), key=lambda value: (int(value.get("timestamp_ns", 0)), int(value.get("sequence", 0))))


def filter_stage_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("raw_action_rad", "candidate_action_rad", "correction_probability",
              "learned_gain", "composed_action_rad", "issued_action_rad")
    counts = {field: sum(record.get(field) is not None for record in records) for field in fields}
    ratios = {field: count / len(records) if records else 0.0 for field, count in counts.items()}
    candidate_rows = [record for record in records if record.get("candidate_action_rad") is not None]
    complete = sum(all(record.get(field) is not None for field in fields) for record in candidate_rows)
    aligned = sum(record.get("filter_inference_stamps_aligned") is True for record in candidate_rows)
    return {"counts": counts, "ratios": ratios, "candidate_rows": len(candidate_rows),
            "complete_candidate_rows": complete,
            "complete_candidate_ratio": 1.0 if not candidate_rows else complete / len(candidate_rows),
            "timestamp_aligned_candidate_rows": aligned,
            "timestamp_aligned_candidate_ratio": 1.0 if not candidate_rows else aligned / len(candidate_rows)}


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
    parser.add_argument("--min-filter-stage-coverage", type=float, default=0.9)
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
    filter_raw_topic = f"/teleop_filter/{opt.arm}/master_joint_raw_rad"
    filter_output_topic = f"/teleop_filter/{opt.arm}/master_joint_filtered_rad"
    filter_candidate_topic = f"/teleop_filter/{opt.arm}/model_candidate_rad"
    filter_diagnostics_topic = f"/teleop_filter/{opt.arm}/diagnostics"
    deployment_output_topic = f"/model_deployment/{opt.arm}_arm_joint_control"
    historical_raw_topic = f"{teleop_ns}/{opt.arm}/master_joint_raw"
    historical_filtered_topic = f"{teleop_ns}/{opt.arm}/master_joint_filtered"
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
    topic_types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    master_raw_topic = filter_raw_topic if filter_raw_topic in topic_types else historical_raw_topic
    master_filtered_topic = filter_output_topic if filter_output_topic in topic_types else historical_filtered_topic
    message_types: dict[str, Any] = {}
    required = (state_topic, master_raw_topic, master_filtered_topic, command_topic, vendor_command_topic, tcp_pose_topic, rgb_topic, depth_topic)
    missing = [topic for topic in required if topic not in topic_types]
    if state_topic not in topic_types:
        raise SystemExit(f"required state topic missing: {state_topic}")
    master_raw: list[tuple[int, Any]] = []
    master_filtered: list[tuple[int, Any]] = []
    filter_candidates: list[tuple[int, Any]] = []
    filter_diagnostics: list[tuple[int, dict[str, Any]]] = []
    deployment_outputs: list[tuple[int, Any]] = []
    commands: list[tuple[int, Any]] = []
    vendor_commands: list[tuple[int, Any]] = []
    tcp_poses: list[tuple[int, Any]] = []
    rgb_stamps: dict[str, list[int]] = {camera_id: [] for camera_id in camera_ids}
    depth_stamps: dict[str, list[int]] = {camera_id: [] for camera_id in camera_ids}
    tactile_force: list[tuple[int, Any]] = []
    tactile_matrix: list[tuple[int, Any]] = []
    tactile_mass: list[tuple[int, Any]] = []
    task_context: list[tuple[int, Any]] = []
    gripper_states: list[tuple[int, Any]] = []
    audit_events: list[dict[str, Any]] = []
    state_samples: list[tuple[int, int, Any]] = []
    max_age_ns = int(opt.max_camera_age_ms * 1e6)
    max_command_age_ns = int(opt.max_command_age_ms * 1e6)
    event_topic = f"{teleop_ns}/events"
    gripper_state_topic = f"{teleop_ns}/{opt.arm}/gripper_state"
    while reader.has_next():
        topic, raw, bag_time_ns = reader.read_next()
        camera_topic_names = {value for _, _, value, _ in camera_topics} | {value for _, _, _, value in camera_topics}
        if topic not in {state_topic, master_raw_topic, master_filtered_topic, filter_candidate_topic, filter_diagnostics_topic, deployment_output_topic, command_topic, vendor_command_topic, tcp_pose_topic, tactile_force_topic, tactile_matrix_topic, tactile_mass_topic, task_context_topic, sim_context_topic, event_topic, gripper_state_topic} | camera_topic_names:
            continue
        if topic not in message_types:
            message_types[topic] = get_message(topic_types[topic])
        message = deserialize_message(raw, message_types[topic])
        message_stamp_ns = stamp_ns(message, bag_time_ns)
        if topic == event_topic:
            raw_event = getattr(message, "data", "")
            try:
                event = json.loads(raw_event)
            except (TypeError, json.JSONDecodeError):
                event = {"raw": str(raw_event)}
            if not isinstance(event, dict):
                event = {"value": event}
            event.setdefault("timestamp_ns", message_stamp_ns)
            event.setdefault("receipt_stamp_ns", int(bag_time_ns))
            event.setdefault("severity", "info")
            event.setdefault("source", "rosbag:/teleop/events")
            event.setdefault("payload", {})
            audit_events.append(event)
            continue
        if topic == master_raw_topic:
            master_raw.append((message_stamp_ns, message))
            continue
        if topic == master_filtered_topic:
            master_filtered.append((message_stamp_ns, message))
            continue
        if topic == filter_candidate_topic:
            filter_candidates.append((message_stamp_ns, message))
            continue
        if topic == filter_diagnostics_topic:
            try:
                payload = json.loads(getattr(message, "data", ""))
            except (TypeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                diagnostic_stamp = int(payload.get("header_stamp_ns") or payload.get("timestamp_ns") or message_stamp_ns)
                filter_diagnostics.append((diagnostic_stamp, payload))
            continue
        if topic == deployment_output_topic:
            deployment_outputs.append((message_stamp_ns, message))
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
        if topic == gripper_state_topic:
            gripper_states.append((message_stamp_ns, message))
            continue
        state_samples.append((message_stamp_ns, int(bag_time_ns), message))

    for stamps in (*rgb_stamps.values(), *depth_stamps.values()):
        stamps.sort()
    state_samples, duplicate_state_timestamps_dropped = deduplicate_state_samples(state_samples)

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
        # Keep the export causal: a state at t may only use an image captured at
        # or before t.  Choosing the nearest frame can accidentally attach a
        # future observation and leak information into filter training/replay.
        index = bisect.bisect_right(stamps, state_stamp_ns) - 1
        if index < 0:
            return None
        frame_stamp = stamps[index]
        if state_stamp_ns - frame_stamp > max_age_ns:
            return None
        return {
            "topic": topic_name,
            "header_stamp_ns": frame_stamp,
            "age_ms": (state_stamp_ns - frame_stamp) / 1e6,
            "alignment": "latest_header_stamp_not_after_state",
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

    def make_stamped_lookup(samples: list[tuple[int, Any]]):
        samples.sort(key=lambda item: item[0])
        stamps = [item[0] for item in samples]
        def lookup(state_stamp_ns: int) -> tuple[int, Any] | None:
            index = bisect.bisect_right(stamps, state_stamp_ns) - 1
            if index < 0 or state_stamp_ns - stamps[index] > max_command_age_ns:
                return None
            return samples[index]
        return lookup

    raw_for = make_command_lookup(master_raw)
    filtered_for = make_command_lookup(master_filtered)
    candidate_for = make_command_lookup(filter_candidates)
    diagnostic_for = make_command_lookup(filter_diagnostics)
    deployment_for = make_command_lookup(deployment_outputs)
    command_for = make_command_lookup(commands)
    vendor_for = make_command_lookup(vendor_commands)
    pose_for = make_command_lookup(tcp_poses)
    context_for = make_command_lookup(task_context)
    gripper_for = make_command_lookup(gripper_states)
    candidate_entry_for = make_stamped_lookup(filter_candidates)
    composed_entry_for = make_stamped_lookup(master_filtered)
    diagnostic_entry_for = make_stamped_lookup(filter_diagnostics)
    deployment_entry_for = make_stamped_lookup(deployment_outputs)
    issued_entry_for = make_stamped_lookup(commands)

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
        candidate = candidate_for(message_stamp_ns)
        diagnostic = diagnostic_for(message_stamp_ns)
        deployment = deployment_for(message_stamp_ns)
        vendor = vendor_for(message_stamp_ns)
        pose = pose_for(message_stamp_ns)
        context = context_for(message_stamp_ns)
        gripper = gripper_for(message_stamp_ns)
        candidate_entry = candidate_entry_for(message_stamp_ns)
        composed_entry = composed_entry_for(message_stamp_ns)
        diagnostic_entry = diagnostic_entry_for(message_stamp_ns)
        deployment_entry = deployment_entry_for(message_stamp_ns)
        issued_entry = issued_entry_for(message_stamp_ns)
        filter_stage_stamps = {
            "candidate": None if candidate_entry is None else candidate_entry[0],
            "composed": None if composed_entry is None else composed_entry[0],
            "diagnostics": None if diagnostic_entry is None else diagnostic_entry[0],
            "issued": None if issued_entry is None else issued_entry[0],
        }
        inference_stamps = [filter_stage_stamps[name] for name in ("candidate", "composed", "diagnostics") if filter_stage_stamps[name] is not None]
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
            "raw_action_rad": None if raw is None else [float(value) for value in raw.position],
            "candidate_action_rad": None if candidate is None else [float(value) for value in candidate.position],
            "correction_probability": None if diagnostic is None else diagnostic.get("correction_probability"),
            "learned_gain": None if diagnostic is None else diagnostic.get("alpha"),
            "composed_action_rad": None if filtered is None else [float(value) for value in filtered.position],
            "issued_action_rad": None if command is None else [float(value) for value in command.position],
            "issued_action_coordinate_space": "vendor_robot_joint",
            "filter_inference_header_stamp_ns": None if diagnostic is None else int(diagnostic.get("header_stamp_ns") or diagnostic.get("timestamp_ns", 0)),
            "filter_authority_mode": None if diagnostic is None else diagnostic.get("authority_mode"),
            "filter_safety_reasons": None if diagnostic is None else diagnostic.get("safety_reasons"),
            "filter_visual_embedding": None if diagnostic is None else diagnostic.get("visual_embedding"),
            "filter_stage_header_stamps_ns": filter_stage_stamps,
            "filter_inference_stamps_aligned": bool(inference_stamps) and len(set(inference_stamps)) == 1,
            "robot_joint_state_rad": [float(value) for value in message.position],
            "mapped_joint_command_rad": None if command is None else [float(value) for value in command.position],
            "controller_command_rad": controller_command,
            "controller_command_source": controller_source,
            "executed_joint_command_rad": controller_command,
            "executed_action_source": controller_source or "recorded_vendor_command",
            "tcp_pose_base": tcp_pose,
            "tcp_pose_frame": tcp_frame,
            "task_context": context_value(context),
            "gripper_state": (int(getattr(gripper, "data")) if gripper is not None and int(getattr(gripper, "data", 255)) in (0, 1) else None),
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
    local_event_sidecar = opt.bag.parent / "audit_events.jsonl" if opt.bag.is_dir() else None
    audit_events = merge_audit_events(audit_events, local_event_sidecar)
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
            "filter_candidate": filter_candidate_topic,
            "filter_diagnostics": filter_diagnostics_topic,
            "deployment_output": deployment_output_topic,
            "command": command_topic,
            "vendor_command": vendor_command_topic,
            "tcp_pose": tcp_pose_topic,
            "rgb": rgb_topic,
            "depth": depth_topic,
            "tactile_force": tactile_force_topic,
            "tactile_matrix": tactile_matrix_topic,
            "tactile_mass": tactile_mass_topic,
            "task_context": task_context_topic if task_context_topic in topic_types else sim_context_topic,
            "gripper_state": gripper_state_topic,
            "events": event_topic if event_topic in topic_types else None,
            "cameras": {camera_id: {"rgb": rgb_topic_name, "depth": depth_topic_name} for camera_id, _, rgb_topic_name, depth_topic_name in camera_topics},
        },
        "missing_topics": missing,
        "camera_alignment": {"policy": "latest_header_stamp_not_after_state", "maximum_age_ms": opt.max_camera_age_ms},
        "command_alignment": {"policy": "latest_header_stamp_not_after_state", "maximum_age_ms": opt.max_command_age_ms},
        "compression_handling": compression_mode,
        "tactile_alignment": {"policy": "latest_header_or_bag_stamp_not_after_state", "maximum_age_ms": opt.max_command_age_ms},
        "tactile_topics_available": {"force": tactile_force_topic in topic_types, "matrix": tactile_matrix_topic in topic_types, "mass": tactile_mass_topic in topic_types},
        "task_context_topic_available": task_context_topic in topic_types or sim_context_topic in topic_types,
        "gripper_state_topic_available": gripper_state_topic in topic_types,
        "sample_count": len(records),
        "audit_event_count": len(audit_events),
        "timestamp_integrity": {
            "state_samples_with_duplicate_header_stamp_dropped": duplicate_state_timestamps_dropped,
            "duplicate_policy": "retain_latest_bag_receipt_per_header_stamp",
        },
        "hardware_accessed": False,
    }
    filter_present = filter_candidate_topic in topic_types or filter_diagnostics_topic in topic_types
    coverage = filter_stage_coverage(records)
    coverage.update({"filter_topics_present": filter_present, "minimum_required": opt.min_filter_stage_coverage})
    manifest["filter_stage_coverage"] = coverage
    manifest_path = opt.output.with_suffix(opt.output.suffix + ".manifest.json")
    events_path = opt.output.with_suffix(opt.output.suffix + ".events.jsonl")
    events_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in audit_events), encoding="utf-8")
    manifest["audit_events_sidecar"] = str(events_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    effective_coverage = min(coverage["complete_candidate_ratio"], coverage["timestamp_aligned_candidate_ratio"])
    if filter_present and coverage["candidate_rows"] == 0:
        effective_coverage = 0.0
    if filter_present and effective_coverage < opt.min_filter_stage_coverage:
        raise SystemExit(f"filter-stage field/timestamp coverage {effective_coverage:.3f} is below required {opt.min_filter_stage_coverage:.3f}; see {manifest_path}")
    if temporary is not None:
        temporary.cleanup()
    print(json.dumps({"output": str(opt.output), "manifest": str(manifest_path), "samples": len(records), "missing_topics": missing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
