#!/usr/bin/env python3
"""Materialize an exported ROS bag arm stream as teleop_episode/v0.1.

This adapter is intentionally conservative.  A raw capture is audit-only until
an explicit terminal audit is supplied and every filter-training causal field
is present.  In particular, a controller command is never relabelled as an
observed action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ADAPTER_VERSION = "exported-jsonl-to-canonical/v0.1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stream_ref(path: Path, available: bool = True, reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"storage_ref": str(path), "timestamp_field": "timestamp_ns", "availability": "available" if available else "unavailable"}
    if not available:
        result["unavailable_reason"] = reason or "not_recorded_by_source"
    return result


def git_revision(root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def causal_row_complete(row: dict[str, Any]) -> bool:
    return all(isinstance(row.get(key), list) and row[key] for key in (
        "raw_teleop", "filter_output", "safety_projected", "controller_command", "robot_state",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source", choices=("real", "simulation"), required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-family", default="connector_insertion")
    parser.add_argument("--success-spec-version", default="usb_c_insertion_v1")
    parser.add_argument("--configuration-id", default="unspecified")
    parser.add_argument("--calibration-version", default="unrecorded")
    parser.add_argument("--collection-mode", choices=("generated", "teleop_rule", "teleop_learned", "replay"), default="teleop_rule")
    parser.add_argument("--terminal-audit", type=Path, help="Explicit structured terminal audit JSON")
    parser.add_argument("--control-hz", type=float, default=100.0)
    args = parser.parse_args()

    rows = read_jsonl(args.export_jsonl)
    if not rows:
        raise SystemExit("export JSONL has no rows")
    episode_id = str(rows[0].get("episode_id") or args.export_jsonl.stem)
    arm = str(rows[0].get("arm", "unknown"))
    joint_names = list(rows[0].get("joint_names") or [])
    if not joint_names:
        raise SystemExit("export JSONL does not declare joint_names")

    output = args.output_dir
    streams = output / "streams"
    streams.mkdir(parents=True, exist_ok=True)
    control_rows: list[dict[str, Any]] = []
    command_rows: list[dict[str, Any]] = []
    tactile_rows: list[dict[str, Any]] = []
    camera_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    for row in rows:
        timestamp = int(row["header_stamp_ns"])
        controller = row.get("controller_command_rad")
        observed = row.get("executed_joint_command_rad")
        control_rows.append({
            "timestamp_ns": timestamp,
            "robot": {"joint_names": joint_names, "q_rad": row.get("robot_joint_state_rad"), "ee_pose_B": row.get("tcp_pose_base"), "ee_pose_frame": row.get("tcp_pose_frame")},
            "execution": {"controller_command": controller, "controller_command_source": row.get("controller_command_source"), "observed_action": observed},
        })
        command_rows.append({
            "timestamp_ns": timestamp,
            "raw_teleop": {"value": row.get("master_joint_raw"), "availability": "available" if row.get("master_joint_raw") else "unavailable", "unavailable_reason": None if row.get("master_joint_raw") else "missing_from_bag"},
            "filter_output": {"value": row.get("master_joint_filtered_rad"), "availability": "available" if row.get("master_joint_filtered_rad") else "unavailable", "unavailable_reason": None if row.get("master_joint_filtered_rad") else "missing_from_bag"},
            "safety_projected": {"value": row.get("mapped_joint_command_rad"), "availability": "available" if row.get("mapped_joint_command_rad") else "unavailable", "unavailable_reason": None if row.get("mapped_joint_command_rad") else "missing_from_bag"},
            "controller_command_ref": timestamp,
            "controller_command": controller,
        })
        if isinstance(row.get("task_context"), dict):
            context_rows.append({"timestamp_ns": timestamp, **row["task_context"]})
        tactile = {name: row.get(name) for name in ("tactile_force", "tactile_matrix", "tactile_mass") if row.get(name) is not None}
        if tactile:
            tactile_rows.append({"timestamp_ns": timestamp, "samples": tactile})
        for name in ("rgb", "depth"):
            if row.get(name) is not None:
                camera_rows.append({"timestamp_ns": timestamp, "camera_id": name, "reference": row[name]})

    def write(name: str, payload: list[dict[str, Any]]) -> Path:
        path = streams / name
        path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in payload), encoding="utf-8")
        return path

    control_path = write("control.jsonl", control_rows)
    commands_path = write("commands.jsonl", command_rows)
    context_path = write("task_context.jsonl", context_rows)
    events_path = write("events.jsonl", [])
    tactile_path = write("tactile.jsonl", tactile_rows)
    cameras_path = write("cameras.jsonl", camera_rows)
    audit: dict[str, Any] = {"success": False, "termination_reason": "not_audited", "safety_violation": False, "unlogged_external_override": True}
    if args.terminal_audit:
        audit.update(json.loads(args.terminal_audit.read_text(encoding="utf-8")))
    causal_complete = all(causal_row_complete({
        "raw_teleop": row.get("master_joint_raw"), "filter_output": row.get("master_joint_filtered_rad"),
        "safety_projected": row.get("mapped_joint_command_rad"), "controller_command": row.get("controller_command_rad"),
        "robot_state": row.get("robot_joint_state_rad"),
    }) for row in rows)
    # Geometry context and observed action are optional extensions.  The core
    # flywheel records command stages, measured state, outcome, and safety.
    context_complete = len(context_rows) == len(rows)
    failed_gates = []
    if not causal_complete:
        failed_gates.append("incomplete_causal_record")
    if audit.get("success") is not True:
        failed_gates.append("terminal_not_success")
    if audit.get("safety_violation") is not False:
        failed_gates.append("safety_violation")
    if audit.get("unlogged_external_override") is not False:
        failed_gates.append("unlogged_external_override")
    admitted = not failed_gates
    audit.update({"buffer": "A_action" if admitted else "A_audit", "admission_rule_version": "A_action/v0.1", "failed_gates": failed_gates})
    manifest = {
        "schema_version": "teleop_episode/v0.1", "episode_id": episode_id, "source": args.source,
        "collection_mode": args.collection_mode, "intended_uses": ["filter_training", "policy_training"] if admitted else ["audit_only"],
        "task": {"task_id": args.task_id, "task_family": args.task_family, "success_spec_version": args.success_spec_version},
        "configuration": {"configuration_id": args.configuration_id, "parameters": {"arm": arm}, "split": "unspecified"},
        "clock": {"clock_domain": "ros2_header", "control_hz": args.control_hz, "timestamp_unit": "ns", "alignment_tolerance_ns": 100_000_000},
        "frames": {"base_frame": "B", "end_effector_frame": "E", "transform_convention": "T_AB maps coordinates in B into A"} if args.calibration_version != "unrecorded" else {},
        "calibration": {"calibration_version": args.calibration_version} if args.calibration_version != "unrecorded" else {},
        "action_spec": {"representation": "joint_position", "frame": "joint_space", "dimension": len(joint_names), "units": ["rad"] * len(joint_names), "controller_interface": "vendor_joint_follow", "joint_names": joint_names},
        "streams": {"control": stream_ref(control_path), "commands": stream_ref(commands_path), "task_context": stream_ref(context_path, context_complete, "no_task_context_publisher_recorded"), "events": stream_ref(events_path), "tactile": stream_ref(tactile_path, bool(tactile_rows), "not_recorded_or_no_tactile_messages"), "cameras": {"recorded_frames": stream_ref(cameras_path, bool(camera_rows), "no_camera_messages_aligned")}},
        "terminal_audit": audit,
        "data_integrity": {"synchronization_valid": causal_complete, "complete_causal_record": causal_complete, "validator_report_ref": "validator_report.json"},
        "provenance": {"code_revision": git_revision(Path(__file__).resolve().parents[1]), "adapter_version": ADAPTER_VERSION, "source_dataset_or_run": str(args.export_jsonl.resolve()), "content_sha256": hashlib.sha256(args.export_jsonl.read_bytes()).hexdigest()},
    }
    manifest_path = output / "episode.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Keep validation evidence beside the immutable manifest.  Audit-only
    # episodes are expected to pass structural validation despite not being
    # eligible for filter training.
    from validate_canonical_episode import validate_manifest, validate_rows
    failures = validate_manifest(manifest)
    failures.extend(validate_rows(control_rows))
    report_path = output / "validator_report.json"
    report_path.write_text(json.dumps({
        "schema": "robot_teleop.canonical-validator/v0.1", "episode_id": episode_id,
        "source": args.source, "passed": not failures, "failure_reasons": failures,
    }, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("canonical adapter produced invalid record: " + ", ".join(failures))
    print(json.dumps({"manifest": str(manifest_path), "episode_id": episode_id, "buffer": audit["buffer"], "failed_gates": failed_gates}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
