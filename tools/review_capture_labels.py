#!/usr/bin/env python3
"""Create reviewed audit sidecars without mutating raw capture evidence.

The review policy is intentionally explicit for the 2026-09-01 practice batch:
only keys 1, 2 and 4 are retained as task events. All episodes are successful
except the explicitly named final failed episode selected by ``--failed``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_EVENTS = {"approach", "align", "correction_start", "correction_end"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("evidence/teleop"))
    parser.add_argument("--prefix", default="20260901")
    parser.add_argument("--failed", required=True, help="episode directory name reviewed as the only failure")
    args = parser.parse_args()
    reviewed = 0
    for run_dir in sorted(args.root.glob(f"{args.prefix}*")):
        artifacts = run_dir / "artifacts"
        events_path = artifacts / "audit_events.jsonl"
        audit_path = artifacts / "terminal_audit.json"
        if not (events_path.is_file() and audit_path.is_file()):
            continue
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        kept = [event for event in events if event.get("event_type") in ALLOWED_EVENTS]
        reviewed_events = artifacts / "audit_events_reviewed.jsonl"
        reviewed_events.write_text(
            "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in kept),
            encoding="utf-8",
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        is_failed = run_dir.name == args.failed
        audit["success"] = not is_failed
        audit["audit_source"] = "manual_structured_reviewed"
        audit["review"] = {
            "policy": "practice_labels_removed_success_reconciled_v1",
            "source_terminal_audit": "terminal_audit.json",
            "source_events": "audit_events.jsonl",
            "retained_event_types": sorted(ALLOWED_EVENTS),
            "removed_event_count": len(events) - len(kept),
            "success_reconciled": True,
        }
        if is_failed:
            audit["termination_reason"] = "reviewed_task_failure"
        else:
            audit["termination_reason"] = "reviewed_task_success"
        (artifacts / "terminal_audit_reviewed.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (artifacts / "label_review.json").write_text(
            json.dumps({
                "schema": "robot_teleop.audit-review/v0.1",
                "source_events": "audit_events.jsonl",
                "reviewed_events": "audit_events_reviewed.jsonl",
                "source_terminal_audit": "terminal_audit.json",
                "reviewed_terminal_audit": "terminal_audit_reviewed.json",
                "removed_event_count": len(events) - len(kept),
                "retained_event_count": len(kept),
                "success": not is_failed,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        reviewed += 1
    print(json.dumps({"reviewed_episodes": reviewed, "failed_episode": args.failed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
