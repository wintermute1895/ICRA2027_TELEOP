#!/usr/bin/env python3
"""Build an admitted correction-segment action-training view.

This adapter is deliberately explicit about the action source. It never
invents a residual from controller-minus-raw; the selected recorded action is
copied into ``expert_action_target_rad`` and the auditor events become a
timestamp-aligned correction mask.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def timestamp(row: dict[str, Any]) -> int:
    value = row.get("timestamp_ns", row.get("header_stamp_ns"))
    if not isinstance(value, int):
        raise ValueError("every row/event must contain integer timestamp_ns or header_stamp_ns")
    return value


def event_mask(rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[bool]:
    ordered = sorted(events, key=timestamp)
    active = False
    event_index = 0
    mask: list[bool] = []
    for row in rows:
        stamp = timestamp(row)
        while event_index < len(ordered) and timestamp(ordered[event_index]) <= stamp:
            kind = ordered[event_index].get("event_type")
            if kind == "correction_start":
                active = True
            elif kind == "correction_end":
                active = False
            event_index += 1
        if isinstance(row.get("correction_active"), bool):
            active = row["correction_active"]
        elif isinstance(row.get("correction_interval"), list) and len(row["correction_interval"]) == 2:
            start, end = row["correction_interval"]
            active = int(start) <= len(mask) <= int(end)
        mask.append(active)
    if active:
        raise ValueError("correction_start has no matching correction_end")
    return mask


def action_value(row: dict[str, Any], field: str) -> list[float]:
    value: Any = row
    for part in field.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"row lacks explicit expert action field: {field}")
        value = value[part]
    if not isinstance(value, list) or not value:
        raise ValueError(f"expert action field is not a non-empty list: {field}")
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError) as error:
        raise ValueError(f"expert action field contains non-numeric values: {field}") from error
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--events", type=Path, help="human auditor events JSONL")
    parser.add_argument("--expert-action-field", required=True, help="recorded action field copied as expert target")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--correction-weight", type=float, default=2.0)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite output: {args.output}")
    if args.correction_weight < 0.0:
        raise SystemExit("--correction-weight must be non-negative")
    rows = read_jsonl(args.episode)
    if not rows:
        raise SystemExit("episode is empty")
    events = read_jsonl(args.events) if args.events else []
    try:
        mask = event_mask(rows, events)
        targets = [action_value(row, args.expert_action_field) for row in rows]
    except ValueError as error:
        raise SystemExit(str(error)) from error
    dimensions = {len(target) for target in targets}
    if len(dimensions) != 1:
        raise SystemExit("expert action dimension changes within episode")
    output_rows = []
    for row, active, target in zip(rows, mask, targets):
        enriched = dict(row)
        enriched["correction_active"] = active
        enriched["correction_mask"] = 1 if active else 0
        enriched["correction_segment_source"] = "human_verified" if args.events else "existing_episode_annotation"
        enriched["expert_action_target_rad"] = target
        enriched["action_target_source"] = "recorded_expert_action"
        output_rows.append(enriched)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows), encoding="utf-8"
    )
    manifest = {
        "schema": "robot_teleop.correction-segment-view/v0.1",
        "source_episode": str(args.episode.resolve()),
        "source_episode_sha256": hashlib.sha256(args.episode.read_bytes()).hexdigest(),
        "source_events": None if args.events is None else str(args.events.resolve()),
        "source_events_sha256": None if args.events is None else hashlib.sha256(args.events.read_bytes()).hexdigest(),
        "expert_action_field": args.expert_action_field,
        "action_target_source": "recorded_expert_action",
        "correction_segment_source": "human_verified" if args.events else "existing_episode_annotation",
        "correction_weight": args.correction_weight,
        "rows": len(output_rows),
        "correction_rows": sum(mask),
    }
    args.output.with_suffix(args.output.suffix + ".manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "rows": len(output_rows), "correction_rows": sum(mask)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
