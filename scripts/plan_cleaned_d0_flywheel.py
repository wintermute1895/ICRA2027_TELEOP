#!/usr/bin/env python3
"""Create the next offline flywheel plan from cleaned D0 episode reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


THRESHOLDS = {"tracking": 0.15, "velocity": 1.50, "acceleration": 8.0, "jerk": 80.0}


def segments(rows: list[dict[str, Any]], fps: int) -> list[dict[str, Any]]:
    flagged = []
    previous_state = previous_velocity = previous_acceleration = None
    dt = 1.0 / fps
    for row in rows:
        state, command = row["robot_joint_state_rad"], row["mapped_joint_command_rad"]
        tracking = max(abs(goal - measured) for goal, measured in zip(command, state))
        velocity = acceleration = jerk = None
        if previous_state is not None:
            current_velocity = [(value - old) / dt for old, value in zip(previous_state, state)]
            velocity = max(abs(value) for value in current_velocity)
            if previous_velocity is not None:
                current_acceleration = [(value - old) / dt for old, value in zip(previous_velocity, current_velocity)]
                acceleration = max(abs(value) for value in current_acceleration)
                if previous_acceleration is not None:
                    jerk = max(abs(value - old) / dt for old, value in zip(previous_acceleration, current_acceleration))
                previous_acceleration = current_acceleration
            previous_velocity = current_velocity
        reasons = []
        if tracking > THRESHOLDS["tracking"]: reasons.append("tracking_error")
        if (velocity or 0.0) > THRESHOLDS["velocity"]: reasons.append("velocity")
        if (acceleration or 0.0) > THRESHOLDS["acceleration"]: reasons.append("acceleration")
        if (jerk or 0.0) > THRESHOLDS["jerk"]: reasons.append("jerk")
        if reasons:
            flagged.append({"sample_index": row["sample_index"], "reasons": reasons, "tracking_error_rad": tracking, "jerk_rad_s3": jerk})
        previous_state = state
    grouped: list[dict[str, Any]] = []
    for item in flagged:
        if not grouped or item["sample_index"] > grouped[-1]["end_sample_index"] + 3:
            grouped.append({"start_sample_index": item["sample_index"], "end_sample_index": item["sample_index"], "reasons": set(item["reasons"]), "items": [item]})
        else:
            group = grouped[-1]
            group["end_sample_index"] = item["sample_index"]
            group["reasons"].update(item["reasons"])
            group["items"].append(item)
    return [{"start_sample_index": group["start_sample_index"], "end_sample_index": group["end_sample_index"],
             "reasons": sorted(group["reasons"]), "flagged_sample_count": len(group["items"]),
             "peak_tracking_error_rad": max(item["tracking_error_rad"] for item in group["items"]),
             "peak_jerk_rad_s3": max(item["jerk_rad_s3"] or 0.0 for item in group["items"])} for group in grouped]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleaned-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.cleaned_root.resolve()
    audits = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((root / "audits").glob("d0_right_hand_*.json"))]
    accepted, replay_queue = [], []
    for audit in audits:
        common = {"episode_id": audit["episode_id"], "success_label": audit["success_label"], "cleaned_episode": audit["cleaned_episode"],
                  "output_samples": audit["output_samples"], "metrics": audit["metrics"], "condition_id": audit.get("condition_id", "unassigned"),
                  "condition_role": audit.get("condition_role", "unassigned")}
        if audit["data_quality_gate"] == "pass" and audit["trajectory_quality_gate"] == "pass":
            accepted.append(common)
            continue
        rows = [json.loads(line) for line in Path(audit["cleaned_episode"]).read_text(encoding="utf-8").splitlines() if line.strip()]
        hard_cases = segments(rows, int(audit["resample_fps"]))
        failed_metrics = [name for name, values in audit["metrics"].items() if name in {"tracking_error_rad", "velocity_rad_s", "acceleration_rad_s2", "jerk_rad_s3"} and values["p95"] is not None]
        replay_queue.append({**common, "priority": 10 * len(hard_cases) + len(failed_metrics), "hard_case_count": len(hard_cases), "hard_cases": hard_cases})
    replay_queue.sort(key=lambda item: (-item["priority"], item["episode_id"]))
    with (root / "high_confidence_registry.jsonl").open("w", encoding="utf-8") as stream:
        for item in accepted: stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    plan = {"schema": "robot_teleop.cleaned-d0-flywheel-plan/v1", "mode": "offline_recommendation_only", "hardware_accessed": False,
            "high_confidence_episode_count": len(accepted), "high_confidence_episodes": accepted,
            "replay_queue": replay_queue,
            "next_collection_requirements": ["Record a condition_id for every future episode.", "Use the same 10 Hz canonical export after capture.", "Review top replay segments before defining a new collection target."],
            "notes": ["All source bags remain read only.", "A replay queue is an analysis priority, never an autonomous robot command."]}
    (root / "next_round_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"high_confidence_episode_count": len(accepted), "replay_queue_count": len(replay_queue), "output": str(root / "next_round_plan.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
