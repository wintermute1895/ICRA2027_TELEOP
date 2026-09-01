#!/usr/bin/env python3
"""Validate immutable capture artifacts after an episode is finalized."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def validate(run_dir: Path, *, require_terminal_audit: bool = False) -> list[str]:
    failures: list[str] = []
    artifacts = run_dir / "artifacts"
    bag = artifacts / "rosbag2"
    if not (bag / "metadata.yaml").is_file():
        failures.append("rosbag_metadata_missing")
    if not list(bag.glob("*.db3")) and not list(bag.glob("*.db3.zstd")):
        failures.append("rosbag_database_missing")
    manifest_path = artifacts / "teleop_capture_manifest.json"
    if not manifest_path.is_file():
        failures.append("capture_manifest_missing")
    else:
        try:
            manifest = load_json(manifest_path)
            if manifest.get("schema") != "robot_teleop.teleop-capture/v1":
                failures.append("capture_manifest_schema_invalid")
            if not manifest.get("topics"):
                failures.append("capture_topics_empty")
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append("capture_manifest_invalid")
    audit_path = artifacts / "terminal_audit.json"
    if require_terminal_audit and not audit_path.is_file():
        failures.append("terminal_audit_missing")
    if audit_path.is_file():
        try:
            audit = load_json(audit_path)
            if audit.get("schema") != "robot_teleop.terminal-audit/v0.1":
                failures.append("terminal_audit_schema_invalid")
            if not isinstance(audit.get("success"), bool):
                failures.append("terminal_audit_success_invalid")
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append("terminal_audit_invalid")
    events_path = artifacts / "audit_events.jsonl"
    if events_path.is_file():
        active = False
        previous_stamp = None
        try:
            for index, line in enumerate(events_path.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                event = json.loads(line)
                stamp = event.get("timestamp_ns")
                if not isinstance(stamp, int):
                    failures.append(f"event_{index}_timestamp_invalid")
                if previous_stamp is not None and isinstance(stamp, int) and stamp < previous_stamp:
                    failures.append("audit_event_timestamps_decrease")
                previous_stamp = stamp if isinstance(stamp, int) else previous_stamp
                if event.get("event_type") == "correction_start":
                    if active:
                        failures.append("correction_started_twice")
                    active = True
                elif event.get("event_type") == "correction_end":
                    if not active:
                        failures.append("correction_ended_without_start")
                    active = False
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append("audit_events_invalid")
        if active:
            failures.append("correction_interval_unclosed")
    return sorted(set(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--require-terminal-audit", action="store_true")
    args = parser.parse_args()
    failures = validate(args.run_dir, require_terminal_audit=args.require_terminal_audit)
    report = {"schema": "robot_teleop.capture-artifact-validation/v0.1", "run_dir": str(args.run_dir.resolve()), "passed": not failures, "failures": failures}
    print(json.dumps(report, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
