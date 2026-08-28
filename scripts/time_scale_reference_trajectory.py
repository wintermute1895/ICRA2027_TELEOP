#!/usr/bin/env python3
"""Create a conservative, time-scaled copy of a fixed joint reference path."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np


def load_csv(path: Path) -> tuple[list[str], np.ndarray, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        if not rows:
            raise ValueError("trajectory CSV is empty")
        names = list(rows[0].keys())[2:]
        if len(names) != 7:
            raise ValueError("trajectory CSV must contain seven joint columns")
        times = np.asarray([float(row["time_from_start_s"]) for row in rows], dtype=np.float64)
        joints = np.asarray([[float(row[name]) for name in names] for row in rows], dtype=np.float64)
    if not np.all(np.isfinite(times)) or not np.all(np.isfinite(joints)):
        raise ValueError("trajectory CSV contains non-finite values")
    if abs(times[0]) > 1e-9 or np.any(np.diff(times) <= 0.0):
        raise ValueError("trajectory timestamps must start at zero and strictly increase")
    return names, times, joints


def metrics(times: np.ndarray, joints: np.ndarray) -> dict[str, float]:
    intervals = np.diff(times)
    velocity = np.diff(joints, axis=0) / intervals[:, None]
    velocity_intervals = (intervals[:-1] + intervals[1:]) / 2.0
    acceleration = np.diff(velocity, axis=0) / velocity_intervals[:, None]
    acceleration_intervals = (velocity_intervals[:-1] + velocity_intervals[1:]) / 2.0
    jerk = np.diff(acceleration, axis=0) / acceleration_intervals[:, None]
    return {
        "velocity_max_rad_s": float(np.max(np.abs(velocity))),
        "acceleration_max_rad_s2": float(np.max(np.abs(acceleration))),
        "jerk_max_rad_s3": float(np.max(np.abs(jerk))),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--max-velocity-rad-s", type=float, default=0.05)
    parser.add_argument("--max-acceleration-rad-s2", type=float, default=0.10)
    parser.add_argument("--max-jerk-rad-s3", type=float, default=0.50)
    args = parser.parse_args()
    if args.fps <= 0.0 or min(args.max_velocity_rad_s, args.max_acceleration_rad_s2, args.max_jerk_rad_s3) <= 0.0:
        raise ValueError("fps and all motion limits must be positive")
    names, times, joints = load_csv(args.input)
    original = metrics(times, joints)
    scale = max(
        1.0,
        original["velocity_max_rad_s"] / args.max_velocity_rad_s,
        math.sqrt(original["acceleration_max_rad_s2"] / args.max_acceleration_rad_s2),
        (original["jerk_max_rad_s3"] / args.max_jerk_rad_s3) ** (1.0 / 3.0),
    )
    limits = {
        "velocity_max_rad_s": args.max_velocity_rad_s,
        "acceleration_max_rad_s2": args.max_acceleration_rad_s2,
        "jerk_max_rad_s3": args.max_jerk_rad_s3,
    }
    step = 1.0 / args.fps
    for _attempt in range(8):
        duration = times[-1] * scale
        scaled_times = np.arange(0.0, duration + step * 0.5, step)
        if scaled_times[-1] < duration:
            scaled_times = np.append(scaled_times, duration)
        else:
            scaled_times[-1] = duration
        scaled_joints = np.stack([np.interp(scaled_times / scale, times, joints[:, index]) for index in range(7)], axis=1)
        shaped = metrics(scaled_times, scaled_joints)
        additional_scale = max(
            1.0,
            shaped["velocity_max_rad_s"] / limits["velocity_max_rad_s"],
            math.sqrt(shaped["acceleration_max_rad_s2"] / limits["acceleration_max_rad_s2"]),
            (shaped["jerk_max_rad_s3"] / limits["jerk_max_rad_s3"]) ** (1.0 / 3.0),
        )
        if additional_scale <= 1.001:
            break
        scale *= additional_scale * 1.001
    else:
        raise RuntimeError(f"resampled trajectory exceeded requested limits: {shaped}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample_index", "time_from_start_s", *names])
        for index, (timestamp, row) in enumerate(zip(scaled_times, scaled_joints)):
            writer.writerow([index, f"{timestamp:.6f}", *(f"{value:.9f}" for value in row)])
    report = {
        "schema": "robot_teleop.conservative-reference-trajectory-report/v1",
        "mode": "offline_only_not_hardware_authorization",
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "fps": args.fps,
        "time_scale_factor": scale,
        "original_duration_s": float(times[-1]),
        "scaled_duration_s": float(scaled_times[-1]),
        "original_samples": len(times),
        "scaled_samples": len(scaled_times),
        "software_motion_targets": limits,
        "original_metrics": original,
        "scaled_metrics": shaped,
        "note": "This software time scaling does not validate controller limits, collision clearance, or hardware safety.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"time_scale_factor": scale, "scaled_duration_s": scaled_times[-1], "scaled_metrics": shaped}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
