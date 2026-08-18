#!/usr/bin/env python3
"""Train the simulation-only causal command filter from audited JSONL episodes.

Accepted episodes must contain causal raw/mapped commands, executed joint state,
and an explicit ``success: true`` record.  The tool never creates ROS nodes or
contacts hardware.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros2_ws/src/sim_robot_driver"))

from sim_robot_driver.causal_filter import build_feature, train_ridge  # noqa: E402
from episode_analysis_common import finite_vector, load_jsonl  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, action="append", required=True, help="audited canonical JSONL; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history-length", type=int, default=8)
    parser.add_argument("--ridge", type=float, default=1e-3)
    args = parser.parse_args()
    if args.history_length < 1:
        parser.error("--history-length must be positive")

    features, targets, rejected = [], [], 0
    joint_count: int | None = None
    for episode_path in args.episode:
        records = load_jsonl(episode_path)
        count = len(records[0].get("joint_names", []))
        if count < 1 or (joint_count is not None and count != joint_count):
            raise SystemExit(f"inconsistent joint count in {episode_path}")
        joint_count = count
        commands = [finite_vector(record.get("mapped_joint_command_rad"), count) for record in records]
        states = [finite_vector(record.get("robot_joint_state_rad"), count) for record in records]
        executed = [finite_vector(record.get("executed_joint_command_rad"), count) for record in records]
        targets_for_episode = [value if value is not None else commands[index] for index, value in enumerate(executed)]
        for index in range(args.history_length - 1, len(records)):
            history = commands[index - args.history_length + 1:index + 1]
            if records[index].get("success") is not True or any(value is None for value in history) or states[index] is None or targets_for_episode[index] is None:
                rejected += 1
                continue
            features.append(build_feature(history, states[index], count, args.history_length))
            targets.append(targets_for_episode[index])
    if joint_count is None or not features:
        raise SystemExit("no accepted training samples; require explicit success=true and complete causal records")
    model = train_ridge(features, targets, joint_count=joint_count, history_length=args.history_length, ridge=args.ridge)
    model.save(args.output)
    print({"model": str(args.output), "training_samples": model.training_samples, "rejected_samples": rejected, "joint_count": joint_count})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
