#!/usr/bin/env python3
"""Project canonical v0.1 materialized streams into the filter-training view."""
from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path
from typing import Any

from validate_canonical_episode import validate_manifest


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def index_rows(rows: list[dict[str, Any]]) -> tuple[list[int], dict[int, dict[str, Any]]]:
    indexed = {int(row["timestamp_ns"]): row for row in rows if "timestamp_ns" in row}
    return sorted(indexed), indexed


def latest(stamps: list[int], rows: dict[int, dict[str, Any]], stamp: int, tolerance: int) -> dict[str, Any] | None:
    position = bisect.bisect_right(stamps, stamp) - 1
    if position < 0 or stamp - stamps[position] > tolerance:
        return None
    return rows[stamps[position]]


def get(row: dict[str, Any] | None, *paths: str) -> Any:
    if row is None:
        return None
    for path in paths:
        current: Any = row
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current is not None:
            return current
    return None


def admitted(manifest: dict[str, Any]) -> bool:
    terminal = manifest.get("terminal_audit", {})
    integrity = manifest.get("data_integrity", {})
    return (
        "filter_training" in manifest.get("intended_uses", [])
        and terminal.get("buffer") == "A_action"
        and terminal.get("success") is True
        and terminal.get("safety_violation") is False
        and terminal.get("unlogged_external_override") is False
        and integrity.get("complete_causal_record") is True
        and integrity.get("synchronization_valid") is True
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--control-jsonl", type=Path, required=True)
    parser.add_argument("--commands-jsonl", type=Path, required=True)
    parser.add_argument("--task-context-jsonl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alignment-tolerance-ns", type=int, default=None)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "teleop_episode/v0.1":
        raise SystemExit("manifest must use schema_version teleop_episode/v0.1")
    manifest_failures = validate_manifest(manifest, require_filter_training=True)
    if manifest_failures or not admitted(manifest):
        raise SystemExit("manifest is not admitted to filter_training/A_action: " + ", ".join(manifest_failures))
    tolerance = args.alignment_tolerance_ns
    if tolerance is None:
        tolerance = int(manifest.get("clock", {}).get("alignment_tolerance_ns", 100_000_000))
    controls, commands = load_jsonl(args.control_jsonl), load_jsonl(args.commands_jsonl)
    contexts = load_jsonl(args.task_context_jsonl) if args.task_context_jsonl else []
    command_stamps, command_rows = index_rows(commands)
    context_stamps, context_rows = index_rows(contexts)
    action_spec = manifest.get("action_spec", {})
    if action_spec.get("representation") not in {"joint_delta", "joint_position", "controller_native"}:
        raise SystemExit("this narrow adapter only supports joint-space/controller-native actions; project Cartesian actions separately")
    joint_names = action_spec.get("joint_names", [])
    if not joint_names or int(action_spec.get("dimension", 0)) != len(joint_names):
        raise SystemExit("joint-space action_spec must declare matching joint_names and dimension")
    output: list[dict[str, Any]] = []
    for index, control in enumerate(controls):
        stamp = int(control["timestamp_ns"])
        command = latest(command_stamps, command_rows, stamp, tolerance)
        context = latest(context_stamps, context_rows, stamp, tolerance)
        raw = get(command, "raw_teleop.value")
        filtered = get(command, "filter_output.value")
        projected = get(command, "safety_projected.value", "execution.controller_command")
        state = get(control, "robot.q_rad")
        controller = get(control, "execution.controller_command")
        if not all(isinstance(item, list) for item in (raw, filtered, projected, state)):
            continue
        if not isinstance(controller, list):
            continue
        row: dict[str, Any] = {
            "schema": "robot_teleop.episode/v1", "episode_id": manifest["episode_id"],
            "source_domain": manifest["source"], "sample_index": index, "header_stamp_ns": stamp,
            "arm": manifest.get("configuration", {}).get("arm", "unknown"), "joint_names": joint_names,
            "master_joint_raw": raw, "filter_output_action": filtered,
            "mapped_joint_command_rad": projected,
            "controller_command_rad": controller,
            "executed_joint_command_rad": get(control, "execution.observed_action"),
            "robot_joint_state_rad": state, "success": True,
        }
        if context is not None:
            context_values = get(context, "filter_context")
            if not isinstance(context_values, list):
                relative_pose = get(context, "target.relative_pose_RP", "target_relative_pose")
                progress = get(context, "reference.progress", "reference_progress")
                visible = get(context, "target.visibility_valid", "visibility_valid")
                if isinstance(relative_pose, list) and isinstance(progress, (int, float)) and isinstance(visible, bool):
                    context_values = [*relative_pose, float(progress), 1.0 if visible else 0.0]
            if isinstance(context_values, list) and len(context_values) == 8:
                row["filter_context"] = list(context_values)
        output.append(row)
    if not output:
        raise SystemExit("no complete causal rows could be projected")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "episode_id": manifest["episode_id"], "samples": len(output), "admitted": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
