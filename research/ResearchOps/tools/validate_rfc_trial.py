#!/usr/bin/env python3
"""Validate an offline RFC trial manifest and append-only event log."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REQUIRED_MANIFEST = {
    "schema", "trial_id", "geometry_id", "initial_dataset_sha256",
    "candidate_pool_sha256", "validation_distribution_sha256",
    "held_out_target_distribution_sha256", "conditions", "budgets",
}
REQUIRED_BUDGET = {
    "candidate_opportunities_exposed", "attempted_queries", "rejected_queries",
    "oracle_queries", "corrected_horizon_steps", "unique_accepted_episodes",
    "unique_training_frames", "duplicated_or_replayed_frames", "training_updates",
}
REQUIRED_SELECTION = {
    "pre_query_score_inputs", "history_cutoff_round", "score_components", "selection_rank",
}
REQUIRED_RESULT = {"selected_event_id", "post_query_audit_labels", "observed_after_selection"}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: event is not an object")
        value["_line"] = line_number
        events.append(value)
    return events


def missing(record: dict[str, Any], fields: set[str]) -> list[str]:
    return sorted(field for field in fields if field not in record)


def validate(manifest_path: Path, events_path: Path) -> tuple[dict[str, Any], int]:
    issues: list[str] = []
    manifest = read_json(manifest_path)
    missing_manifest = missing(manifest, REQUIRED_MANIFEST)
    issues.extend(f"manifest missing {field}" for field in missing_manifest)

    conditions = manifest.get("conditions", [])
    if not isinstance(conditions, list) or not conditions or not all(isinstance(item, dict) for item in conditions):
        issues.append("manifest conditions must be a non-empty list of objects")
        conditions = []
    condition_ids = [item.get("condition_id") for item in conditions]
    if len(set(condition_ids)) != len(condition_ids) or None in condition_ids:
        issues.append("manifest condition_id values must be unique and non-null")
    for condition in conditions:
        cid = condition.get("condition_id", "<missing>")
        for field in ("condition_id", "allocation_rule_version", "random_seed"):
            if field not in condition:
                issues.append(f"condition {cid}: missing {field}")
        budget = manifest.get("budgets", {}).get(cid) if isinstance(manifest.get("budgets"), dict) else None
        if not isinstance(budget, dict):
            issues.append(f"condition {cid}: missing budget")
        else:
            issues.extend(f"condition {cid}: budget missing {field}" for field in sorted(REQUIRED_BUDGET - set(budget)))

    expected_trial = manifest.get("trial_id")
    expected_conditions = set(condition_ids)
    events = read_jsonl(events_path)
    event_ids: set[str] = set()
    selected: dict[str, dict[str, Any]] = {}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        line = event["_line"]
        prefix = f"event line {line}"
        event_ids.add(str(event.get("event_id")))
        for field in ("event_id", "trial_id", "condition_id", "round", "candidate_id", "event_type", "recorded_at_unix_ns"):
            if field not in event:
                issues.append(f"{prefix}: missing {field}")
        if event.get("trial_id") != expected_trial:
            issues.append(f"{prefix}: trial_id does not match manifest")
        cid = event.get("condition_id")
        if cid not in expected_conditions:
            issues.append(f"{prefix}: unknown condition {cid}")
        event_type = event.get("event_type")
        counts[str(cid)][str(event_type)] += 1
        try:
            round_id = int(event.get("round"))
        except (TypeError, ValueError):
            issues.append(f"{prefix}: round must be an integer")
            round_id = -1
        if event_type == "candidate_selected":
            issues.extend(f"{prefix}: selection missing {field}" for field in sorted(REQUIRED_SELECTION - set(event)))
            if "post_query_audit_labels" in event or "oracle_outcome" in event:
                issues.append(f"{prefix}: selection contains post-query information")
            try:
                if int(event.get("history_cutoff_round")) >= round_id:
                    issues.append(f"{prefix}: history cutoff must precede current round")
            except (TypeError, ValueError):
                issues.append(f"{prefix}: history_cutoff_round must be an integer")
            if event.get("event_id") in selected:
                issues.append(f"{prefix}: duplicate selection event_id")
            selected[str(event.get("event_id"))] = event
            if cid == "B3_no_rec":
                components = event.get("score_components")
                if not isinstance(components, dict):
                    issues.append(f"{prefix}: B3_no_rec score_components must be an object")
                else:
                    history_names = {"recoverability", "historical_recoverability", "uncertainty", "failure", "abstention", "contact", "outcome"}
                    for name in history_names.intersection(components):
                        if components[name] not in (0, 0.0, None, False):
                            issues.append(f"{prefix}: B3_no_rec history component {name} is non-zero")
        elif event_type == "query_result":
            issues.extend(f"{prefix}: result missing {field}" for field in sorted(REQUIRED_RESULT - set(event)))
            selected_event = selected.get(str(event.get("selected_event_id")))
            if selected_event is None:
                issues.append(f"{prefix}: result does not reference a prior selection")
            elif selected_event.get("candidate_id") != event.get("candidate_id"):
                issues.append(f"{prefix}: result candidate differs from selection")
            if event.get("observed_after_selection") is not True:
                issues.append(f"{prefix}: observed_after_selection must be true")
        elif event_type == "budget_snapshot":
            issues.extend(f"{prefix}: budget snapshot missing {field}" for field in REQUIRED_BUDGET - set(event))
        else:
            issues.append(f"{prefix}: unsupported event_type {event_type}")

    if len(event_ids) != len(events):
        issues.append("event_id values must be unique")
    result = {
        "schema": "vist.researchops.rfc-trial-validation/v1",
        "status": "pass" if not issues else "fail",
        "trial_id": expected_trial,
        "conditions": sorted(expected_conditions, key=str),
        "event_count": len(events),
        "event_counts": {cid: dict(values) for cid, values in sorted(counts.items())},
        "issues": issues,
        "note": "Pass means the artifact contract is internally consistent; it does not establish safety, task success, or algorithmic superiority.",
    }
    return result, 0 if not issues else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = validate(args.manifest, args.events)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
