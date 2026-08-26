#!/usr/bin/env python3
"""Run a read-only data-flywheel analysis over D0 right-arm ROS2 bags."""
from __future__ import annotations

import argparse
import bisect
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


TOPICS = {
    "state": "/robot1/right_arm/joint_states",
    "command": "/vist/right/mapped_joint_command",
    "raw": "/vist/right/master_joint_raw",
    "filtered": "/vist/right/master_joint_filtered",
    "rgb": "/camera/camera/color/image_raw",
    "depth": "/camera/camera/depth/image_rect_raw",
}
MAX_ALIGNMENT_AGE_NS = 100_000_000
QUALITY = {"minimum_samples": 30, "coverage": 0.99, "camera_coverage": 0.95, "max_gap_ms": 250.0}
TRAJECTORY = {"tracking_rms": 0.12, "tracking_p95": 0.20, "velocity_p95": 1.50, "acceleration_p95": 8.0, "jerk_p95": 80.0}
HARD_CASE = {"tracking": 0.15, "velocity": 1.50, "acceleration": 8.0, "jerk": 80.0}


def stamp_ns(message: Any, fallback: int) -> int:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    value = 0 if stamp is None else int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    return value if value > 0 else int(fallback)


def vector(values: Any, expected: int = 7) -> list[float] | None:
    if len(values) < expected:
        return None
    result = [float(value) for value in values[:expected]]
    return result if all(math.isfinite(value) for value in result) else None


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summary(values: list[float]) -> dict[str, float | None]:
    return {"count": len(values), "rms": math.sqrt(mean([value * value for value in values])) if values else None,
            "p95": percentile(values, 0.95), "maximum": max(values) if values else None}


def nearest_age_ms(stamps: list[int], target: int) -> float | None:
    if not stamps:
        return None
    index = bisect.bisect_left(stamps, target)
    candidates = stamps[max(0, index - 1):index + 1]
    return min(abs(candidate - target) for candidate in candidates) / 1e6


def latest_command(commands: list[tuple[int, list[float]]], stamps: list[int], target: int) -> list[float] | None:
    index = bisect.bisect_right(stamps, target) - 1
    if index < 0 or target - stamps[index] > MAX_ALIGNMENT_AGE_NS:
        return None
    return commands[index][1]


def segment_hard_cases(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for sample in samples:
        reasons = []
        if (sample["tracking_error_max_rad"] or 0.0) > HARD_CASE["tracking"]: reasons.append("tracking_error")
        if (sample["velocity_max_rad_s"] or 0.0) > HARD_CASE["velocity"]: reasons.append("velocity")
        if (sample["acceleration_max_rad_s2"] or 0.0) > HARD_CASE["acceleration"]: reasons.append("acceleration")
        if (sample["jerk_max_rad_s3"] or 0.0) > HARD_CASE["jerk"]: reasons.append("jerk")
        if not reasons:
            continue
        if not segments or sample["sample_index"] > segments[-1]["end_sample_index"] + 3:
            segments.append({"start_sample_index": sample["sample_index"], "end_sample_index": sample["sample_index"], "reasons": set(reasons), "samples": [sample]})
        else:
            segment = segments[-1]
            segment["end_sample_index"] = sample["sample_index"]
            segment["reasons"].update(reasons)
            segment["samples"].append(sample)
    result = []
    for segment in segments:
        flagged = segment["samples"]
        result.append({"start_sample_index": segment["start_sample_index"], "end_sample_index": segment["end_sample_index"],
                       "reasons": sorted(segment["reasons"]), "flagged_sample_count": len(flagged),
                       "peak_tracking_error_rad": max(item["tracking_error_max_rad"] or 0.0 for item in flagged),
                       "peak_jerk_rad_s3": max(item["jerk_max_rad_s3"] or 0.0 for item in flagged)})
    return result


def analyze_episode(episode_dir: Path) -> dict[str, Any]:
    manifest = json.loads((episode_dir / "recording_manifest.json").read_text(encoding="utf-8"))
    bag = episode_dir / "bag"
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="sqlite3"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {item.name: get_message(item.type) for item in reader.get_all_topics_and_types()}
    missing_topics = sorted(topic for topic in TOPICS.values() if topic not in types)
    states: list[tuple[int, list[float]]] = []
    commands: list[tuple[int, list[float]]] = []
    raw_count = filtered_count = 0
    rgb_stamps: list[int] = []
    depth_stamps: list[int] = []
    relevant = set(TOPICS.values())
    while reader.has_next():
        topic, raw, bag_stamp = reader.read_next()
        if topic not in relevant:
            continue
        message = deserialize_message(raw, types[topic])
        stamp = stamp_ns(message, bag_stamp)
        if topic == TOPICS["state"]:
            value = vector(message.position)
            if value is not None: states.append((stamp, value))
        elif topic == TOPICS["command"]:
            value = vector(message.position)
            if value is not None: commands.append((stamp, value))
        elif topic == TOPICS["raw"]:
            raw_count += 1
        elif topic == TOPICS["filtered"]:
            filtered_count += 1
        elif topic == TOPICS["rgb"]:
            rgb_stamps.append(stamp)
        elif topic == TOPICS["depth"]:
            depth_stamps.append(stamp)
    states.sort(key=lambda item: item[0]); commands.sort(key=lambda item: item[0]); rgb_stamps.sort(); depth_stamps.sort()
    command_stamps = [item[0] for item in commands]
    samples: list[dict[str, Any]] = []
    tracking, velocities, accelerations, jerks = [], [], [], []
    previous_state = previous_velocity = previous_acceleration = None
    previous_stamp = None
    for index, (stamp, state) in enumerate(states):
        command = latest_command(commands, command_stamps, stamp)
        rgb_age, depth_age = nearest_age_ms(rgb_stamps, stamp), nearest_age_ms(depth_stamps, stamp)
        tracking_error = max(abs(left - right) for left, right in zip(state, command)) if command else None
        if tracking_error is not None: tracking.append(tracking_error)
        velocity = acceleration = jerk = None
        if previous_stamp is not None and stamp > previous_stamp:
            dt = (stamp - previous_stamp) / 1e9
            velocity_vector = [(value - old) / dt for old, value in zip(previous_state, state)]
            velocity = max(abs(value) for value in velocity_vector); velocities.append(velocity)
            if previous_velocity is not None:
                acceleration_vector = [(value - old) / dt for old, value in zip(previous_velocity, velocity_vector)]
                acceleration = max(abs(value) for value in acceleration_vector); accelerations.append(acceleration)
                if previous_acceleration is not None:
                    jerk_vector = [(value - old) / dt for old, value in zip(previous_acceleration, acceleration_vector)]
                    jerk = max(abs(value) for value in jerk_vector); jerks.append(jerk)
                previous_acceleration = acceleration_vector
            previous_velocity = velocity_vector
        samples.append({"sample_index": index, "header_stamp_ns": stamp, "tracking_error_max_rad": tracking_error,
                        "velocity_max_rad_s": velocity, "acceleration_max_rad_s2": acceleration, "jerk_max_rad_s3": jerk,
                        "rgb_age_ms": rgb_age, "depth_age_ms": depth_age})
        previous_state, previous_stamp = state, stamp
    periods = [(right[0] - left[0]) / 1e6 for left, right in zip(states, states[1:])]
    command_coverage = sum(sample["tracking_error_max_rad"] is not None for sample in samples) / len(samples) if samples else 0.0
    rgb_coverage = sum(sample["rgb_age_ms"] is not None and sample["rgb_age_ms"] <= 100.0 for sample in samples) / len(samples) if samples else 0.0
    depth_coverage = sum(sample["depth_age_ms"] is not None and sample["depth_age_ms"] <= 100.0 for sample in samples) / len(samples) if samples else 0.0
    increasing = bool(periods) and all(value > 0 for value in periods)
    max_gap = max(periods) if periods else None
    quality_checks = {"minimum_samples": len(samples) >= QUALITY["minimum_samples"], "required_topics": not missing_topics,
                      "state_coverage": bool(samples), "command_coverage": command_coverage >= QUALITY["coverage"],
                      "timestamps": increasing, "maximum_gap": max_gap is not None and max_gap <= QUALITY["max_gap_ms"],
                      "rgb_coverage": rgb_coverage >= QUALITY["camera_coverage"], "depth_coverage": depth_coverage >= QUALITY["camera_coverage"]}
    tracking_summary, velocity_summary = summary(tracking), summary(velocities)
    acceleration_summary, jerk_summary = summary(accelerations), summary(jerks)
    trajectory_checks = {"command_coverage": command_coverage >= QUALITY["coverage"],
                         "tracking_rms": tracking_summary["rms"] is not None and tracking_summary["rms"] <= TRAJECTORY["tracking_rms"],
                         "tracking_p95": tracking_summary["p95"] is not None and tracking_summary["p95"] <= TRAJECTORY["tracking_p95"],
                         "velocity_p95": velocity_summary["p95"] is not None and velocity_summary["p95"] <= TRAJECTORY["velocity_p95"],
                         "acceleration_p95": acceleration_summary["p95"] is not None and acceleration_summary["p95"] <= TRAJECTORY["acceleration_p95"],
                         "jerk_p95": jerk_summary["p95"] is not None and jerk_summary["p95"] <= TRAJECTORY["jerk_p95"]}
    hard_cases = segment_hard_cases(samples)
    return {"schema": "robot_teleop.d0-flywheel-episode-report/v1", "evaluation_mode": "offline_read_only", "hardware_accessed": False,
            "episode_id": manifest["episode_id"], "arm": manifest["arm"], "source_domain": "real", "success_label": manifest.get("outcome", {}).get("status"),
            "task_id": manifest.get("task", {}).get("task_id"), "condition_id": manifest.get("condition_id", "unassigned"),
            "bag": str(bag), "topics": {"missing": missing_topics, "master_raw_count": raw_count, "master_filtered_count": filtered_count},
            "data_quality": {"quality_gate": "pass" if all(quality_checks.values()) else "review", "checks": quality_checks,
                             "coverage": {"state": 1.0 if samples else 0.0, "command": command_coverage, "rgb": rgb_coverage, "depth": depth_coverage},
                             "timing": {"strictly_increasing": increasing, "median_period_ms": median(periods) if periods else None, "maximum_gap_ms": max_gap}},
            "trajectory_quality": {"trajectory_quality_gate": "pass" if all(trajectory_checks.values()) else "review", "checks": trajectory_checks,
                                   "metrics": {"tracking_error_rad": tracking_summary, "velocity_rad_s": velocity_summary, "acceleration_rad_s2": acceleration_summary, "jerk_rad_s3": jerk_summary}},
            "hard_cases": {"hard_case_count": len(hard_cases), "segments": hard_cases}, "sample_count": len(samples)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--start", type=int, default=100)
    parser.add_argument("--end", type=int, default=139)
    args = parser.parse_args()
    output = args.output_root.resolve(); episode_output = output / "episodes"; episode_output.mkdir(parents=True, exist_ok=True)
    registry = []; failures = []
    for number in range(args.start, args.end + 1):
        episode_dir = args.input_root / f"d0_right_hand_{number}"
        try:
            report = analyze_episode(episode_dir)
            report_path = episode_output / f"{report['episode_id']}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            registry.append({"episode_id": report["episode_id"], "arm": report["arm"], "source_domain": report["source_domain"],
                             "success_label": report["success_label"], "task_id": report["task_id"], "condition_id": report["condition_id"],
                             "data_quality_gate": report["data_quality"]["quality_gate"], "trajectory_quality_gate": report["trajectory_quality"]["trajectory_quality_gate"],
                             "hard_case_count": report["hard_cases"]["hard_case_count"], "analysis_eligible": report["data_quality"]["quality_gate"] == "pass" and report["trajectory_quality"]["trajectory_quality_gate"] == "pass", "report": str(report_path)})
            print(json.dumps({"episode_id": report["episode_id"], "quality": report["data_quality"]["quality_gate"], "trajectory": report["trajectory_quality"]["trajectory_quality_gate"], "hard_cases": report["hard_cases"]["hard_case_count"]}))
        except Exception as exc:
            failures.append({"episode_dir": str(episode_dir), "error": str(exc)})
            print(json.dumps({"episode_dir": str(episode_dir), "error": str(exc)}))
    with (output / "episode_registry.jsonl").open("w", encoding="utf-8") as stream:
        for record in registry: stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    replay_queue = sorted([record for record in registry if not record["analysis_eligible"] or record["hard_case_count"] > 0], key=lambda item: (item["analysis_eligible"], -item["hard_case_count"], item["episode_id"]))
    plan = {"schema": "robot_teleop.d0-flywheel-plan/v1", "mode": "offline_recommendation_only", "hardware_accessed": False,
            "replay_queue": replay_queue, "metadata_gaps": ["condition_id is unassigned for all current episodes; do not use this run for A/B comparison."],
            "notes": ["Original ROS bags were read only.", "Hard cases are review and replay priorities, not robot commands."]}
    (output / "next_round_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"episode_count": len(registry), "analysis_eligible_count": sum(item["analysis_eligible"] for item in registry), "failure_count": len(failures), "failures": failures, "output_root": str(output)}
    (output / "run_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
