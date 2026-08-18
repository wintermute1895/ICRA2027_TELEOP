#!/usr/bin/env python3
"""Validate a canonical teleop_episode/v0.1 manifest and optional JSONL rows.

The validator is source agnostic: simulation and real manifests use the same
checks. It never deletes or rewrites the canonical record.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def finite_vector(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value)


def validate_manifest(manifest: dict[str, Any], *, require_filter_training: bool = False) -> list[str]:
    failures: list[str] = []
    required = ("schema_version", "episode_id", "source", "collection_mode", "intended_uses", "task", "configuration", "clock", "frames", "calibration", "action_spec", "streams", "terminal_audit", "data_integrity", "provenance")
    failures.extend(f"missing:{key}" for key in required if key not in manifest)
    if manifest.get("schema_version") != "teleop_episode/v0.1":
        failures.append("schema_version")
    streams = manifest.get("streams", {})
    for name in ("control", "task_context", "events"):
        if name not in streams:
            failures.append(f"streams.{name}.missing")
    action = manifest.get("action_spec", {})
    for name in ("representation", "frame", "dimension", "units", "controller_interface"):
        if name not in action:
            failures.append(f"action_spec.{name}.missing")
    terminal = manifest.get("terminal_audit", {})
    integrity = manifest.get("data_integrity", {})
    filter_requested = require_filter_training or "filter_training" in manifest.get("intended_uses", [])
    if filter_requested:
        if "commands" not in streams:
            failures.append("streams.commands.missing")
        if terminal.get("buffer") != "A_action":
            failures.append("terminal_audit.buffer_not_A_action")
        for key in ("success", "safety_violation", "unlogged_external_override"):
            if terminal.get(key) is not (True if key == "success" else False):
                failures.append(f"terminal_audit.{key}")
        for key in ("complete_causal_record", "synchronization_valid"):
            if integrity.get(key) is not True:
                failures.append(f"data_integrity.{key}")
    return failures


def validate_rows(rows: list[dict[str, Any]], *, require_executed: bool = False) -> list[str]:
    failures: list[str] = []
    previous = None
    for index, row in enumerate(rows):
        stamp = row.get("timestamp_ns", row.get("header_stamp_ns"))
        if not isinstance(stamp, int):
            failures.append(f"row[{index}].timestamp_ns")
        elif previous is not None and stamp <= previous:
            failures.append(f"row[{index}].timestamp_not_strictly_increasing")
        previous = stamp if isinstance(stamp, int) else previous
        fields = {"raw_teleop": ("raw_teleop", "master_joint_raw"), "filter_output": ("filter_output", "filter_output_action"), "safety_projected": ("safety_projected", "mapped_joint_command_rad"), "robot_joint_state_rad": ("robot_joint_state_rad",)}
        for canonical_name, alternatives in fields.items():
            present = next((field for field in alternatives if field in row), None)
            if present is not None and not finite_vector(row[present]):
                failures.append(f"row[{index}].{canonical_name}")
        if require_executed:
            required_causal_fields = {"raw_teleop": ("raw_teleop", "master_joint_raw"), "filter_output": ("filter_output", "filter_output_action"), "safety_projected": ("safety_projected", "mapped_joint_command_rad"), "robot_joint_state_rad": ("robot_joint_state_rad",)}
            for canonical_name, alternatives in required_causal_fields.items():
                if not any(field in row and finite_vector(row[field]) for field in alternatives):
                    failures.append(f"row[{index}].{canonical_name}_missing")
            if not finite_vector(row.get("executed_joint_command_rad")):
                failures.append(f"row[{index}].executed_joint_command_rad_missing")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rows", type=Path)
    parser.add_argument("--require-filter-training", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    failures = validate_manifest(manifest, require_filter_training=args.require_filter_training)
    if args.rows:
        rows = [json.loads(line) for line in args.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
        failures.extend(validate_rows(rows, require_executed=args.require_filter_training or "filter_training" in manifest.get("intended_uses", [])))
    report = {
        "schema": "robot_teleop.canonical-validator/v0.1",
        "episode_id": manifest.get("episode_id"),
        "source": manifest.get("source"),
        "filter_training_requested": args.require_filter_training or "filter_training" in manifest.get("intended_uses", []),
        "passed": not failures,
        "failure_reasons": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
