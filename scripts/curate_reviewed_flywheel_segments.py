#!/usr/bin/env python3
"""Apply conservative data-review decisions to cleaned flywheel episodes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


MIN_ACCEPTED_SAMPLES = 10


def complement(length: int, blocked: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(blocked):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    result, cursor = [], 0
    for start, end in merged:
        if cursor < start:
            result.append((cursor, start - 1))
        cursor = end + 1
    if cursor < length:
        result.append((cursor, length - 1))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleaned-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.cleaned_root.resolve()
    plan = json.loads((root / "next_round_plan.json").read_text(encoding="utf-8"))
    review_by_episode = {item["episode_id"]: item for item in plan["replay_queue"]}
    audits = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((root / "audits").glob("d0_right_hand_*.json"))]
    decisions, curated = [], []
    for audit in audits:
        episode_id = audit["episode_id"]
        row_count = audit["output_samples"]
        fps = int(audit["resample_fps"])
        common = {"episode_id": episode_id, "success_label": audit["success_label"], "cleaned_episode": audit["cleaned_episode"], "fps": fps,
                  "condition_id": audit.get("condition_id", "unassigned"), "condition_role": audit.get("condition_role", "unassigned")}
        review = review_by_episode.get(episode_id)
        if review is None:
            decisions.append({**common, "review_decision": "accept_for_training", "reason": "passes_cleaned_data_and_trajectory_gates"})
            curated.append({**common, "start_sample_index": 0, "end_sample_index": row_count - 1, "duration_s": row_count / fps, "source": "high_confidence_episode"})
            continue
        blocked = []
        for segment in review["hard_cases"]:
            start, end = segment["start_sample_index"], segment["end_sample_index"]
            blocked.append((start, end))
            decisions.append({**common, "start_sample_index": start, "end_sample_index": end, "review_decision": "exclude_from_training", "reason": "trajectory_threshold_exceeded", "signals": segment["reasons"]})
        accepted_ranges = complement(row_count, blocked)
        retained = 0
        for start, end in accepted_ranges:
            if end - start + 1 < MIN_ACCEPTED_SAMPLES:
                decisions.append({**common, "start_sample_index": start, "end_sample_index": end, "review_decision": "exclude_from_training", "reason": "stable_span_shorter_than_one_second"})
                continue
            retained += end - start + 1
            curated.append({**common, "start_sample_index": start, "end_sample_index": end, "duration_s": (end - start + 1) / fps, "source": "review_episode_stable_span"})
        decisions.append({**common, "review_decision": "needs_recollection" if retained < MIN_ACCEPTED_SAMPLES else "accept_stable_spans_only", "reason": "review_episode_segmented_by_trajectory_quality", "retained_samples": retained, "total_samples": row_count})
    package = root / "review_package"
    with (package / "review_decisions.jsonl").open("w", encoding="utf-8") as stream:
        for item in decisions: stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (root / "curated_training_segments.jsonl").open("w", encoding="utf-8") as stream:
        for item in curated: stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary = {"episode_count": len(audits), "accepted_segment_count": len(curated), "accepted_sample_count": sum(item["end_sample_index"] - item["start_sample_index"] + 1 for item in curated), "excluded_hard_segment_count": sum(item.get("review_decision") == "exclude_from_training" and item.get("reason") == "trajectory_threshold_exceeded" for item in decisions), "needs_recollection_episode_count": sum(item.get("review_decision") == "needs_recollection" for item in decisions)}
    (package / "review_decision_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
