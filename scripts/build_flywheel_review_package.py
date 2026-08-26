#!/usr/bin/env python3
"""Create a human-review manifest for the cleaned flywheel replay queue."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleaned-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.cleaned_root.resolve()
    plan = json.loads((root / "next_round_plan.json").read_text(encoding="utf-8"))
    items = []
    for episode in plan["replay_queue"]:
        audit = json.loads((root / "audits" / f"{episode['episode_id']}.json").read_text(encoding="utf-8"))
        fps = int(audit["resample_fps"])
        for index, segment in enumerate(episode["hard_cases"], 1):
            items.append({
                "review_id": f"{episode['episode_id']}-segment-{index:03d}",
                "episode_id": episode["episode_id"],
                "source_bag": audit["source_bag"],
                "cleaned_episode": episode["cleaned_episode"],
                "start_sample_index": segment["start_sample_index"],
                "end_sample_index": segment["end_sample_index"],
                "start_time_s": segment["start_sample_index"] / fps,
                "end_time_s": segment["end_sample_index"] / fps,
                "reasons": segment["reasons"],
                "priority": episode["priority"],
                "review_status": "pending",
                "review_decision": None,
                "review_note": None,
            })
    output = root / "review_package"
    output.mkdir(parents=True, exist_ok=True)
    with (output / "review_manifest.jsonl").open("w", encoding="utf-8") as stream:
        for item in items:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary = {"pending_segment_count": len(items), "episode_count": len(plan["replay_queue"]),
               "review_decisions": ["accept_for_training", "exclude_from_training", "needs_recollection"],
               "manifest": str(output / "review_manifest.jsonl")}
    (output / "review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
