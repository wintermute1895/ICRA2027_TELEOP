#!/usr/bin/env python3
"""Create cleaned, uniformly sampled D0 episode JSONL files from ROS2 bags.

The source ROS bags are opened read-only. Output contains state/action samples
and references to source camera frames, never copied image pixels.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


TOPICS = {
    "state": "/robot1/right_arm/joint_states",
    "command": "/vist/right/mapped_joint_command",
    "rgb": "/camera/camera/color/image_raw",
    "depth": "/camera/camera/depth/image_rect_raw",
}
MAX_STATE_GAP_NS = 100_000_000
MAX_COMMAND_AGE_NS = 100_000_000
MAX_CAMERA_AGE_NS = 100_000_000


def stamp_ns(message: Any, fallback: int) -> int:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    value = 0 if stamp is None else int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    return value if value > 0 else int(fallback)


def finite_vector(values: Any, dimension: int = 7) -> list[float] | None:
    if len(values) < dimension:
        return None
    result = [float(value) for value in values[:dimension]]
    return result if all(math.isfinite(value) for value in result) else None


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower, upper = math.floor(index), math.ceil(index)
    return ordered[lower] if lower == upper else ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def metric(values: list[float]) -> dict[str, float | int | None]:
    return {"count": len(values), "rms": math.sqrt(mean(value * value for value in values)) if values else None,
            "p95": percentile(values, 0.95), "maximum": max(values) if values else None}


def nearest(stamps: list[int], target: int) -> tuple[int, float] | None:
    if not stamps:
        return None
    index = bisect.bisect_left(stamps, target)
    candidates = stamps[max(0, index - 1):index + 1]
    stamp = min(candidates, key=lambda value: abs(value - target))
    age_ns = abs(stamp - target)
    return (stamp, age_ns / 1e6) if age_ns <= MAX_CAMERA_AGE_NS else None


def interpolate(samples: list[tuple[int, list[float]]], stamps: list[int], target: int) -> list[float] | None:
    right = bisect.bisect_left(stamps, target)
    if right < len(stamps) and stamps[right] == target:
        return samples[right][1]
    if right == 0 or right == len(stamps):
        return None
    left = right - 1
    start, end = stamps[left], stamps[right]
    if end - start > MAX_STATE_GAP_NS:
        return None
    fraction = (target - start) / (end - start)
    return [before + (after - before) * fraction for before, after in zip(samples[left][1], samples[right][1])]


def prior(samples: list[tuple[int, list[float]]], stamps: list[int], target: int) -> list[float] | None:
    index = bisect.bisect_right(stamps, target) - 1
    if index < 0 or target - stamps[index] > MAX_COMMAND_AGE_NS:
        return None
    return samples[index][1]


def read_streams(bag: Path) -> tuple[dict[str, Any], dict[str, list], list[str]]:
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="sqlite3"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {item.name: get_message(item.type) for item in reader.get_all_topics_and_types()}
    missing = [topic for topic in TOPICS.values() if topic not in types]
    streams: dict[str, list] = {"state": [], "command": [], "rgb": [], "depth": []}
    joint_names: list[str] = []
    wanted = set(TOPICS.values())
    while reader.has_next():
        topic, raw, bag_stamp = reader.read_next()
        if topic not in wanted:
            continue
        message = deserialize_message(raw, types[topic])
        stamp = stamp_ns(message, bag_stamp)
        if topic == TOPICS["state"]:
            values = finite_vector(message.position)
            if values is not None:
                streams["state"].append((stamp, values))
                if not joint_names:
                    joint_names = list(message.name[:7])
        elif topic == TOPICS["command"]:
            values = finite_vector(message.position)
            if values is not None:
                streams["command"].append((stamp, values))
        elif topic == TOPICS["rgb"]:
            streams["rgb"].append(stamp)
        elif topic == TOPICS["depth"]:
            streams["depth"].append(stamp)
    for name in streams:
        streams[name].sort(key=lambda item: item[0] if isinstance(item, tuple) else item)
    return streams, {"joint_names": joint_names}, missing


def deduplicate(samples: list[tuple[int, list[float]]]) -> tuple[list[tuple[int, list[float]]], int]:
    by_stamp = {stamp: values for stamp, values in samples}
    return sorted(by_stamp.items()), len(samples) - len(by_stamp)


def clean_episode(episode_dir: Path, output_dir: Path, fps: int) -> dict[str, Any]:
    manifest = json.loads((episode_dir / "recording_manifest.json").read_text(encoding="utf-8"))
    streams, metadata, missing_topics = read_streams(episode_dir / "bag")
    states, duplicate_states = deduplicate(streams["state"])
    commands, duplicate_commands = deduplicate(streams["command"])
    rgb, depth = sorted(set(streams["rgb"])), sorted(set(streams["depth"]))
    drops: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    if missing_topics or not states or not commands or not rgb or not depth:
        drops["missing_required_stream"] += 1
    else:
        state_stamps, command_stamps = [item[0] for item in states], [item[0] for item in commands]
        start, end = max(state_stamps[0], command_stamps[0]), min(state_stamps[-1], command_stamps[-1])
        step_ns = round(1_000_000_000 / fps)
        for target in range(start, end + 1, step_ns):
            state = interpolate(states, state_stamps, target)
            command = prior(commands, command_stamps, target)
            rgb_ref, depth_ref = nearest(rgb, target), nearest(depth, target)
            if state is None: drops["state_gap"] += 1; continue
            if command is None: drops["command_age"] += 1; continue
            if rgb_ref is None: drops["rgb_age"] += 1; continue
            if depth_ref is None: drops["depth_age"] += 1; continue
            records.append({"schema": "robot_teleop.cleaned-episode/v1", "episode_id": manifest["episode_id"],
                            "source_domain": "real", "sample_index": len(records), "header_stamp_ns": target,
                            "arm": "right", "joint_names": metadata["joint_names"], "robot_joint_state_rad": state,
                            "mapped_joint_command_rad": command, "rgb": {"header_stamp_ns": rgb_ref[0], "age_ms": rgb_ref[1]},
                            "depth": {"header_stamp_ns": depth_ref[0], "age_ms": depth_ref[1]},
                            "success": manifest.get("outcome", {}).get("status"), "source_bag": str(episode_dir / "bag")})
    output_path = output_dir / f"{manifest['episode_id']}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    tracking = [max(abs(goal - observed) for goal, observed in zip(record["mapped_joint_command_rad"], record["robot_joint_state_rad"])) for record in records]
    velocity, acceleration, jerk = [], [], []
    previous_state = previous_velocity = previous_acceleration = None
    step_s = 1.0 / fps
    for record in records:
        state = record["robot_joint_state_rad"]
        if previous_state is not None:
            current_velocity = [(value - old) / step_s for old, value in zip(previous_state, state)]
            velocity.append(max(abs(value) for value in current_velocity))
            if previous_velocity is not None:
                current_acceleration = [(value - old) / step_s for old, value in zip(previous_velocity, current_velocity)]
                acceleration.append(max(abs(value) for value in current_acceleration))
                if previous_acceleration is not None:
                    jerk.append(max(abs(value - old) / step_s for old, value in zip(previous_acceleration, current_acceleration)))
                previous_acceleration = current_acceleration
            previous_velocity = current_velocity
        previous_state = state
    quality_gate = "pass" if len(records) >= 30 and not missing_topics else "review"
    trajectory_gate = "pass" if (metric(tracking)["rms"] or math.inf) <= 0.12 and (metric(tracking)["p95"] or math.inf) <= 0.20 and (metric(velocity)["p95"] or math.inf) <= 1.5 and (metric(acceleration)["p95"] or math.inf) <= 8.0 and (metric(jerk)["p95"] or math.inf) <= 80.0 else "review"
    return {"episode_id": manifest["episode_id"], "success_label": manifest.get("outcome", {}).get("status"), "source_bag": str(episode_dir / "bag"),
            "cleaned_episode": str(output_path), "resample_fps": fps, "input": {"state_samples": len(streams["state"]), "command_samples": len(streams["command"]), "rgb_frames": len(streams["rgb"]), "depth_frames": len(streams["depth"]), "duplicate_state_timestamps_removed": duplicate_states, "duplicate_command_timestamps_removed": duplicate_commands, "missing_topics": missing_topics},
            "output_samples": len(records), "dropped_samples": dict(drops), "data_quality_gate": quality_gate, "trajectory_quality_gate": trajectory_gate,
            "metrics": {"tracking_error_rad": metric(tracking), "velocity_rad_s": metric(velocity), "acceleration_rad_s2": metric(acceleration), "jerk_rad_s3": metric(jerk)}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--start", type=int, default=100)
    parser.add_argument("--end", type=int, default=139)
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    if args.fps <= 0:
        parser.error("--fps must be positive")
    output = args.output_root.resolve()
    cleaned_dir = output / "episodes"
    audit_dir = output / "audits"
    audit_dir.mkdir(parents=True, exist_ok=True)
    audits = []
    if args.summarize_only:
        audits = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(audit_dir.glob("d0_right_hand_*.json"))]
    else:
        for number in range(args.start, args.end + 1):
            report = clean_episode(args.input_root / f"d0_right_hand_{number}", cleaned_dir, args.fps)
            (audit_dir / f"{report['episode_id']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            audits.append(report)
            print(json.dumps({"episode_id": report["episode_id"], "output_samples": report["output_samples"], "quality": report["data_quality_gate"], "trajectory": report["trajectory_quality_gate"]}))
    with (output / "cleaning_registry.jsonl").open("w", encoding="utf-8") as stream:
        for audit in audits: stream.write(json.dumps(audit, ensure_ascii=False) + "\n")
    summary = {"episode_count": len(audits), "resample_fps": args.fps, "quality_pass_count": sum(audit["data_quality_gate"] == "pass" for audit in audits), "trajectory_pass_count": sum(audit["trajectory_quality_gate"] == "pass" for audit in audits), "output_root": str(output)}
    (output / "cleaning_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
