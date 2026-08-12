#!/usr/bin/env python3
"""Read-only trajectory-quality evaluation for one canonical episode JSONL."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import yaml

from episode_analysis_common import finite_vector, load_jsonl, max_abs, scalar_summary


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/experiments/trajectory_quality_gate.yaml"


def numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def planning_metric(record: dict[str, Any], names: tuple[str, ...]) -> float | None:
    planning = record.get("planning")
    candidates = [planning] if isinstance(planning, dict) else []
    candidates.append(record)
    for container in candidates:
        for name in names:
            value = numeric(container.get(name))
            if value is not None:
                return value
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    thresholds = config["thresholds"]
    requirements = config["requirements"]
    records = load_jsonl(args.episode)
    joint_count = len(records[0].get("joint_names", []))
    if joint_count <= 0:
        raise SystemExit("episode has no joint_names")

    sample_metrics: list[dict[str, Any]] = []
    previous_state: list[float] | None = None
    previous_velocity: list[float] | None = None
    previous_acceleration: list[float] | None = None
    previous_stamp: int | None = None
    tracking_errors: list[float] = []
    velocity_peaks: list[float] = []
    acceleration_peaks: list[float] = []
    jerk_peaks: list[float] = []
    singular_values: list[float] = []
    clearances: list[float] = []

    for index, record in enumerate(records):
        stamp = record.get("header_stamp_ns")
        state = finite_vector(record.get("robot_joint_state_rad"), joint_count)
        command = finite_vector(record.get("mapped_joint_command_rad"), joint_count)
        dt_s = None
        if isinstance(stamp, int) and previous_stamp is not None and stamp > previous_stamp:
            dt_s = (stamp - previous_stamp) / 1e9
        error_peak = None
        if state is not None and command is not None:
            error_peak = max(abs(target - observed) for target, observed in zip(command, state))
            tracking_errors.append(error_peak)
        velocity = None
        if state is not None and previous_state is not None and dt_s is not None:
            velocity = [(right - left) / dt_s for left, right in zip(previous_state, state)]
            velocity_peaks.append(max_abs(velocity) or 0.0)
        acceleration = None
        if velocity is not None and previous_velocity is not None and dt_s is not None:
            acceleration = [(right - left) / dt_s for left, right in zip(previous_velocity, velocity)]
            acceleration_peaks.append(max_abs(acceleration) or 0.0)
        jerk = None
        if acceleration is not None and previous_acceleration is not None and dt_s is not None:
            jerk = [(right - left) / dt_s for left, right in zip(previous_acceleration, acceleration)]
            jerk_peaks.append(max_abs(jerk) or 0.0)
        singular = planning_metric(record, ("minimum_singular_value", "min_singular_value"))
        clearance = planning_metric(record, ("minimum_clearance_m", "minimum_model_clearance_m", "collision_clearance_m"))
        if singular is not None:
            singular_values.append(singular)
        if clearance is not None:
            clearances.append(clearance)
        sample_metrics.append({
            "sample_index": int(record.get("sample_index", index)),
            "header_stamp_ns": stamp,
            "tracking_error_max_rad": error_peak,
            "velocity_max_rad_s": max_abs(velocity),
            "acceleration_max_rad_s2": max_abs(acceleration),
            "jerk_max_rad_s3": max_abs(jerk),
            "minimum_singular_value": singular,
            "minimum_clearance_m": clearance,
        })
        previous_state = state
        previous_velocity = velocity
        previous_acceleration = acceleration
        previous_stamp = stamp if isinstance(stamp, int) else previous_stamp

    summaries = {
        "tracking_error_rad": scalar_summary(tracking_errors),
        "velocity_rad_s": scalar_summary(velocity_peaks),
        "acceleration_rad_s2": scalar_summary(acceleration_peaks),
        "jerk_rad_s3": scalar_summary(jerk_peaks),
        "minimum_singular_value": scalar_summary(singular_values),
        "minimum_clearance_m": scalar_summary(clearances),
    }
    checks = {
        "mapped_command": (not requirements["require_mapped_command"] or len(tracking_errors) == len(records)),
        "tracking_error_rms": summaries["tracking_error_rad"]["rms"] is not None and summaries["tracking_error_rad"]["rms"] <= thresholds["tracking_error_rms_rad_max"],
        "tracking_error_p95": summaries["tracking_error_rad"]["p95"] is not None and summaries["tracking_error_rad"]["p95"] <= thresholds["tracking_error_p95_rad_max"],
        "velocity_p95": summaries["velocity_rad_s"]["p95"] is not None and summaries["velocity_rad_s"]["p95"] <= thresholds["velocity_p95_rad_s_max"],
        "acceleration_p95": summaries["acceleration_rad_s2"]["p95"] is not None and summaries["acceleration_rad_s2"]["p95"] <= thresholds["acceleration_p95_rad_s2_max"],
        "jerk_p95": summaries["jerk_rad_s3"]["p95"] is not None and summaries["jerk_rad_s3"]["p95"] <= thresholds["jerk_p95_rad_s3_max"],
        "minimum_singular_value": (not requirements["require_planning_singularity_metric"] or (summaries["minimum_singular_value"]["minimum"] is not None and summaries["minimum_singular_value"]["minimum"] >= thresholds["minimum_singular_value_min"])),
        "minimum_clearance_m": (not requirements["require_collision_clearance_metric"] or (summaries["minimum_clearance_m"]["minimum"] is not None and summaries["minimum_clearance_m"]["minimum"] >= thresholds["minimum_clearance_m_min"])),
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "robot_teleop.trajectory-quality-report/v1",
        "evaluation_mode": "offline_read_only",
        "hardware_accessed": False,
        "source_episode": str(args.episode.resolve()),
        "episode_id": records[0].get("episode_id"),
        "source_domain": records[0].get("source_domain"),
        "arm": records[0].get("arm"),
        "sample_count": len(records),
        "joint_count": joint_count,
        "metrics": summaries,
        "checks": checks,
        "trajectory_quality_gate": "pass" if not failures else "review",
        "failure_reasons": failures,
        "sample_metrics": sample_metrics,
        "notes": ["Offline control quality only; not a task-success or real-robot safety authorization."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(__import__("json").dumps(report, indent=2) + "\n", encoding="utf-8")
    print(__import__("json").dumps({"report": str(args.output), "trajectory_quality_gate": report["trajectory_quality_gate"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
