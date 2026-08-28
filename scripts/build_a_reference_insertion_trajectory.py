#!/usr/bin/env python3
"""Extract one repeatable A-condition reference trajectory from successful demos.

This tool is deliberately offline-only. It never opens ROS or sends robot commands.
The selected reference is a medoid: a recorded successful trajectory that is closest
to the other quality-gated demonstrations after phase normalization. Selecting a
real demonstration avoids synthesizing a joint-space average that was never shown
to succeed.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def phase_resample(values: np.ndarray, points: int) -> np.ndarray:
    source_phase = np.linspace(0.0, 1.0, len(values))
    target_phase = np.linspace(0.0, 1.0, points)
    return np.stack([np.interp(target_phase, source_phase, values[:, joint]) for joint in range(values.shape[1])], axis=1)


def p95(values: np.ndarray) -> float:
    return float(np.percentile(values, 95)) if len(values) else 0.0


def dynamics(command: np.ndarray, fps: int) -> dict[str, float]:
    velocity = np.diff(command, axis=0) * fps
    acceleration = np.diff(velocity, axis=0) * fps
    jerk = np.diff(acceleration, axis=0) * fps
    return {
        "velocity_p95_rad_s": p95(np.max(np.abs(velocity), axis=1)),
        "acceleration_p95_rad_s2": p95(np.max(np.abs(acceleration), axis=1)),
        "jerk_p95_rad_s3": p95(np.max(np.abs(jerk), axis=1)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True, help="next_round_plan.json with high_confidence_episodes")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phase-samples", type=int, default=400)
    parser.add_argument("--fps", type=int, default=10)
    args = parser.parse_args()
    if args.phase_samples < 2:
        raise ValueError("--phase-samples must be at least 2")

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    candidates: list[dict] = []
    for item in plan["high_confidence_episodes"]:
        rows = read_jsonl(Path(item["cleaned_episode"]))
        command = np.asarray([row["mapped_joint_command_rad"] for row in rows], dtype=np.float64)
        state = np.asarray([row["robot_joint_state_rad"] for row in rows], dtype=np.float64)
        if len(command) < 2 or command.shape[1] != 7:
            continue
        candidates.append({
            "episode_id": item["episode_id"],
            "rows": rows,
            "command": command,
            "state": state,
            "phase_command": phase_resample(command, args.phase_samples),
            "source_metrics": item["metrics"],
        })
    if len(candidates) < 2:
        raise RuntimeError("need at least two quality-gated episodes")

    phase_stack = np.stack([item["phase_command"] for item in candidates])
    pairwise_rms = np.sqrt(np.mean((phase_stack[:, None] - phase_stack[None, :]) ** 2, axis=(2, 3)))
    medoid_scores = pairwise_rms.mean(axis=1)
    selected_index = int(np.argmin(medoid_scores))
    selected = candidates[selected_index]
    selected_command = selected["command"]
    selected_state = selected["state"]
    joint_names = selected["rows"][0]["joint_names"]

    start_state = np.stack([item["state"][0] for item in candidates])
    start_error = np.abs(start_state - selected_state[0])
    start_l2_error = np.linalg.norm(start_state - selected_state[0], axis=1)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    trajectory_path = output / "reference_trajectory.jsonl"
    with trajectory_path.open("w", encoding="utf-8") as handle:
        for index, row in enumerate(selected["rows"]):
            reference = {
                "schema": "robot_teleop.fixed-reference-trajectory/v1",
                "mode": "offline_reference_only",
                "execution_authorization": False,
                "condition_id": "第一条件",
                "condition_role": "A",
                "reference_id": "a_insertion_medoid_v1",
                "reference_episode_id": selected["episode_id"],
                "sample_index": index,
                "time_from_start_s": index / args.fps,
                "joint_names": joint_names,
                "joint_command_rad": row["mapped_joint_command_rad"],
                "recorded_joint_state_rad": row["robot_joint_state_rad"],
            }
            handle.write(json.dumps(reference, ensure_ascii=False) + "\n")

    csv_path = output / "reference_trajectory.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sample_index", "time_from_start_s", *joint_names])
        for index, values in enumerate(selected_command):
            writer.writerow([index, f"{index / args.fps:.3f}", *(f"{value:.9f}" for value in values)])

    report = {
        "schema": "robot_teleop.fixed-reference-trajectory-report/v1",
        "mode": "offline_reference_only",
        "hardware_accessed": False,
        "execution_authorization": False,
        "condition_id": "第一条件",
        "condition_role": "A",
        "method": "phase_normalized_successful_trajectory_medoid",
        "why_medoid_not_mean": "The reference is one recorded successful path, not an unvalidated pointwise average.",
        "candidate_selection": {
            "quality_gated_successful_episode_count": len(candidates),
            "phase_samples": args.phase_samples,
            "selected_reference_episode_id": selected["episode_id"],
            "selected_medoid_rms_rad": float(medoid_scores[selected_index]),
            "candidate_medoid_rms_rad": {
                item["episode_id"]: float(medoid_scores[index]) for index, item in enumerate(candidates)
            },
        },
        "reference": {
            "fps": args.fps,
            "sample_count": len(selected_command),
            "duration_s": (len(selected_command) - 1) / args.fps,
            "joint_names": joint_names,
            "start_joint_command_rad": selected_command[0].tolist(),
            "end_joint_command_rad": selected_command[-1].tolist(),
            "dynamics": dynamics(selected_command, args.fps),
            "source_quality_metrics": selected["source_metrics"],
        },
        "start_precondition_from_quality_gated_demos": {
            "expected_joint_state_rad": selected_state[0].tolist(),
            "joint_absolute_error_p95_rad": np.percentile(start_error, 95, axis=0).tolist(),
            "joint_absolute_error_max_rad": np.max(start_error, axis=0).tolist(),
            "joint_l2_error_p95_rad": p95(start_l2_error),
            "meaning": "Measure the current state against expected_joint_state_rad before replay; this descriptive envelope is not a validated safety limit.",
        },
        "required_before_any_robot_replay": [
            "Verify current joint state is within an approved start tolerance.",
            "Verify the object, insertion target, gripper state, and fixture match condition A.",
            "Validate joint limits, collision clearance, velocity, acceleration, and jerk on the target controller.",
            "Run in simulation and then supervised reduced-speed trials with an emergency stop.",
        ],
        "artifacts": {
            "trajectory_jsonl": str(trajectory_path),
            "trajectory_csv": str(csv_path),
        },
    }
    (output / "reference_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_reference_episode_id": selected["episode_id"], "duration_s": report["reference"]["duration_s"], "medoid_rms_rad": report["candidate_selection"]["selected_medoid_rms_rad"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
