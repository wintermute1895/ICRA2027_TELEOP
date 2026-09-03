#!/usr/bin/env python3
"""Materialize an exported ROS bag arm stream as teleop_episode/v0.1.

An explicit terminal audit is required for training admission. Cold-start
filter data requires synchronized master action and robot state; closed-loop
captures additionally report whether every command stage was recorded.
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


def stream_ref(
    path: Path,
    available: bool = True,
    reason: str | None = None,
    *,
    relative_to: Path | None = None,
) -> dict[str, Any]:
    storage_ref = path.relative_to(relative_to) if relative_to is not None else path
    result: dict[str, Any] = {"storage_ref": str(storage_ref), "timestamp_field": "timestamp_ns", "availability": "available" if available else "unavailable"}
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


def policy_row_complete(row: dict[str, Any]) -> bool:
    return all(isinstance(row.get(key), list) and row[key] for key in (
        "controller_command_rad", "robot_joint_state_rad",
    )) and isinstance(row.get("rgb"), dict)


def cold_start_filter_row_complete(row: dict[str, Any]) -> bool:
    return all(isinstance(row.get(key), list) and row[key] for key in (
        "master_joint_raw", "robot_joint_state_rad",
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
    parser.add_argument("--events-jsonl", type=Path, help="Auditor events sidecar exported from /teleop/events")
    parser.add_argument("--control-hz", type=float, default=100.0)
    parser.add_argument("--min-policy-complete-ratio", type=float, default=0.95)
    args = parser.parse_args()
    if not 0.0 < args.min_policy_complete_ratio <= 1.0:
        raise SystemExit("--min-policy-complete-ratio must be in (0, 1]")

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
        filter_output = row.get("master_joint_filtered_rad")
        safety_projected = row.get("mapped_joint_command_rad")
        control_rows.append({
            "timestamp_ns": timestamp,
            "robot": {"joint_names": joint_names, "q_rad": row.get("robot_joint_state_rad"), "ee_pose_B": row.get("tcp_pose_base"), "ee_pose_frame": row.get("tcp_pose_frame")},
            "execution": {"controller_command": controller, "controller_command_source": row.get("controller_command_source"), "observed_action": observed},
            "gripper_state": row.get("gripper_state"),
            "gripper_state_semantics": {"0": "open", "1": "closed"},
        })
        command_rows.append({
            "timestamp_ns": timestamp,
            "raw_teleop": {"value": row.get("master_joint_raw"), "availability": "available" if row.get("master_joint_raw") else "unavailable", "unavailable_reason": None if row.get("master_joint_raw") else "missing_from_bag"},
            "filter_output": {"value": filter_output, "availability": "available" if filter_output else "unavailable", "unavailable_reason": None if filter_output else "missing_from_bag"},
            "safety_projected": {"value": safety_projected, "availability": "available" if safety_projected else "unavailable", "unavailable_reason": None if safety_projected else "missing_from_bag"},
            "controller_command_ref": timestamp,
            "controller_command": controller,
            "gripper_state": row.get("gripper_state"),
        })
        if isinstance(row.get("task_context"), dict):
            context_rows.append({"timestamp_ns": timestamp, **row["task_context"]})
        tactile = {name: row.get(name) for name in ("tactile_force", "tactile_matrix", "tactile_mass") if row.get(name) is not None}
        if tactile:
            tactile_rows.append({"timestamp_ns": timestamp, "samples": tactile})
        cameras = row.get("cameras")
        if isinstance(cameras, dict):
            for camera_id, modalities in cameras.items():
                if not isinstance(modalities, dict):
                    continue
                if modalities.get("rgb") is not None:
                    camera_rows.append({
                        "timestamp_ns": timestamp,
                        "camera_id": str(camera_id),
                        "modality": "rgb",
                        "reference": modalities["rgb"],
                    })
                if modalities.get("depth") is not None:
                    camera_rows.append({
                        "timestamp_ns": timestamp,
                        "camera_id": str(camera_id),
                        "modality": "depth",
                        "reference": modalities["depth"],
                    })
        else:
            # Backward compatibility for exports produced before named cameras.
            for name in ("rgb", "depth"):
                if row.get(name) is not None:
                    camera_rows.append({
                        "timestamp_ns": timestamp,
                        "camera_id": name,
                        "modality": name,
                        "reference": row[name],
                    })

    def write(name: str, payload: list[dict[str, Any]]) -> Path:
        path = streams / name
        path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in payload), encoding="utf-8")
        return path

    control_path = write("control.jsonl", control_rows)
    commands_path = write("commands.jsonl", command_rows)
    context_path = write("task_context.jsonl", context_rows)
    events_source = args.events_jsonl
    if events_source is None:
        export_manifest = args.export_jsonl.with_suffix(args.export_jsonl.suffix + ".manifest.json")
        if export_manifest.is_file():
            manifest_value = json.loads(export_manifest.read_text(encoding="utf-8")).get("audit_events_sidecar")
            if manifest_value:
                candidate = Path(manifest_value)
                events_source = candidate if candidate.is_absolute() else export_manifest.parent / candidate
    events = read_jsonl(events_source) if events_source and events_source.is_file() else []
    events_path = write("events.jsonl", events)
    tactile_path = write("tactile.jsonl", tactile_rows)
    cameras_path = write("cameras.jsonl", camera_rows)
    audit: dict[str, Any] = {"success": False, "termination_reason": "not_audited", "safety_violation": False, "unlogged_external_override": True}
    if args.terminal_audit:
        audit.update(json.loads(args.terminal_audit.read_text(encoding="utf-8")))
    causal_rows = sum(causal_row_complete({
        "raw_teleop": row.get("master_joint_raw"), "filter_output": row.get("master_joint_filtered_rad"),
        "safety_projected": row.get("mapped_joint_command_rad"), "controller_command": row.get("controller_command_rad"),
        "robot_state": row.get("robot_joint_state_rad"),
    }) for row in rows)
    # Presence of command-stage fields is not proof that a learned filter was
    # in the control loop.  Cold-start captures commonly contain rule-filter
    # or compatibility fields, but their expert target must remain independent
    # of the learned model.  Only an explicitly learned collection mode can
    # claim a complete learned causal record.
    learned_causal_mode = args.collection_mode in {"teleop_learned", "replay"}
    causal_complete = learned_causal_mode and causal_rows == len(rows)
    policy_rows = sum(policy_row_complete(row) for row in rows)
    policy_complete_ratio = policy_rows / len(rows)
    filter_rows = sum(cold_start_filter_row_complete(row) for row in rows)
    filter_complete_ratio = filter_rows / len(rows)
    # Geometry context and observed action are optional extensions.  The core
    # flywheel records command stages, measured state, outcome, and safety.
    context_complete = len(context_rows) == len(rows)
    outcome_admitted = (
        audit.get("success") is True
        and audit.get("safety_violation") is False
        and audit.get("unlogged_external_override") is False
    )
    policy_admitted = outcome_admitted and policy_complete_ratio >= args.min_policy_complete_ratio
    failed_gates = []
    deferred_gates = []
    if not causal_complete:
        deferred_gates.append("incomplete_causal_record")
    if audit.get("success") is not True:
        failed_gates.append("terminal_not_success")
    if audit.get("safety_violation") is not False:
        failed_gates.append("safety_violation")
    if audit.get("unlogged_external_override") is not False:
        failed_gates.append("unlogged_external_override")
    # Cold-start demonstrations intentionally have no learned-filter output.
    # Recorded expert/controller actions are sufficient to train the first
    # residual filter; the stricter causal gate is for closed-loop rounds.
    cold_start_admitted = outcome_admitted and filter_complete_ratio >= args.min_policy_complete_ratio
    filter_admitted = cold_start_admitted
    intended_uses = []
    if filter_admitted:
        intended_uses.append("filter_training")
    if policy_admitted:
        intended_uses.append("policy_training")
    if not intended_uses:
        intended_uses.append("audit_only")
    audit.update({"buffer": "A_action" if filter_admitted else "A_audit", "admission_rule_version": "A_action/v0.2", "failed_gates": failed_gates, "deferred_gates": deferred_gates,
                  "filter_training_stage": "cold_start_expert" if filter_admitted and not causal_complete else ("closed_loop_filter" if filter_admitted else None)})
    manifest = {
        "schema_version": "teleop_episode/v0.1", "episode_id": episode_id, "source": args.source,
        "collection_mode": args.collection_mode, "intended_uses": intended_uses,
        "task": {"task_id": args.task_id, "task_family": args.task_family, "success_spec_version": args.success_spec_version},
        "configuration": {"configuration_id": args.configuration_id, "parameters": {"arm": arm}, "split": "unspecified"},
        "clock": {"clock_domain": "ros2_header", "control_hz": args.control_hz, "timestamp_unit": "ns", "alignment_tolerance_ns": 100_000_000},
        "frames": {"base_frame": "B", "end_effector_frame": "E", "transform_convention": "T_AB maps coordinates in B into A"} if args.calibration_version != "unrecorded" else {},
        "calibration": {"calibration_version": args.calibration_version} if args.calibration_version != "unrecorded" else {},
        "action_spec": {"representation": "joint_position", "frame": "joint_space", "dimension": len(joint_names), "units": ["rad"] * len(joint_names), "controller_interface": "vendor_joint_follow", "joint_names": joint_names},
        "streams": {
            "control": stream_ref(control_path, relative_to=output),
            "commands": stream_ref(commands_path, relative_to=output),
            "task_context": stream_ref(context_path, context_complete, "no_task_context_publisher_recorded", relative_to=output),
            "events": stream_ref(events_path, relative_to=output),
            "gripper_state": stream_ref(write("gripper_state.jsonl", [{"timestamp_ns": int(row["header_stamp_ns"]), "state": row.get("gripper_state"), "semantics": {"0": "open", "1": "closed"}} for row in rows if row.get("gripper_state") in (0, 1)]), any(row.get("gripper_state") in (0, 1) for row in rows), "not_recorded_by_source", relative_to=output),
            "tactile": stream_ref(tactile_path, bool(tactile_rows), "not_recorded_or_no_tactile_messages", relative_to=output),
            "cameras": {"recorded_frames": stream_ref(cameras_path, bool(camera_rows), "no_camera_messages_aligned", relative_to=output)},
        },
        "terminal_audit": audit,
        "data_integrity": {
            "synchronization_valid": (
                causal_complete
                or filter_complete_ratio >= args.min_policy_complete_ratio
                or policy_complete_ratio >= args.min_policy_complete_ratio
            ),
            "complete_causal_record": causal_complete,
            "causal_complete_rows": causal_rows,
            "filter_complete_rows": filter_rows,
            "filter_complete_ratio": filter_complete_ratio,
            "policy_complete_rows": policy_rows,
            "policy_complete_ratio": policy_complete_ratio,
            "policy_minimum_complete_ratio": args.min_policy_complete_ratio,
            "policy_training_admitted": policy_admitted,
            "filter_training_admitted": filter_admitted,
            "filter_training_stage": "cold_start_expert" if filter_admitted and not causal_complete else ("closed_loop_filter" if filter_admitted else None),
            "deferred_gates": deferred_gates,
            "validator_report_ref": "validator_report.json",
        },
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
