#!/usr/bin/env python3
"""Create a read-only next-round collection and replay queue from a registry."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config/experiments/precision_assembly_ab.yaml"


def load_registry(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args()
    profile = yaml.safe_load(args.profile.read_text(encoding="utf-8"))
    records = load_registry(args.registry)
    target = int(profile["design"]["pilot_valid_episodes_per_condition"])
    eligible = [record for record in records if record.get("analysis_eligible")]
    accepted_by_condition = Counter(record.get("condition_id") for record in eligible)
    collection_targets = [
        {"condition_id": condition, "condition_role": definition.get("role"), "valid_episode_deficit": max(0, target - accepted_by_condition[condition]), "priority": 1 if accepted_by_condition[condition] < target else 0}
        for condition, definition in profile["conditions"].items()
    ]
    replay_queue = []
    for record in records:
        reasons = []
        if record.get("data_quality_gate") != "pass": reasons.append("data_quality")
        if record.get("trajectory_quality_gate") != "pass": reasons.append("trajectory_quality")
        if record.get("hard_case_count", 0) > 0: reasons.append("hard_case")
        if reasons:
            replay_queue.append({
                "registry_key": record["registry_key"],
                "episode_id": record["episode_id"],
                "arm": record["arm"],
                "source_domain": record["source_domain"],
                "condition_id": record["condition_id"],
                "priority": 100 * ("data_quality" in reasons) + 10 * ("trajectory_quality" in reasons) + int(record.get("hard_case_count", 0)),
                "reasons": reasons,
                "reports": record["reports"],
            })
    replay_queue.sort(key=lambda item: (-item["priority"], item["registry_key"]))
    report = {
        "schema": "robot_teleop.data-flywheel-plan/v1",
        "mode": "offline_recommendation_only",
        "hardware_accessed": False,
        "registry": str(args.registry.resolve()),
        "profile": str(args.profile.resolve()),
        "collection_targets": collection_targets,
        "replay_queue": replay_queue,
        "notes": [
            "This plan never launches a robot or publishes commands.",
            "Use replay_queue to improve control, annotation, or scene models before scheduling new data.",
            "Any real collection still requires the capture launcher's safety confirmations.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "replay_queue_count": len(replay_queue), "collection_targets": collection_targets}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
