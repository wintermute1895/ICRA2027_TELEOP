#!/usr/bin/env python3
"""Produce reproducible descriptive A/B reports from an episode registry."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import mean, median
from typing import Any

import yaml

from episode_analysis_common import percentile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config/experiments/precision_assembly_ab.yaml"
DEFAULT_METRICS = ("tracking_error_rms_rad", "tracking_error_p95_rad", "jerk_rms_rad_s3", "hard_case_count")


def load_registry(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    if not records:
        raise SystemExit(f"registry is empty: {path}")
    return records


def values(records: list[dict[str, Any]], metric: str) -> list[float]:
    result = []
    for record in records:
        value = record.get(metric)
        if isinstance(value, (int, float)):
            result.append(float(value))
    return result


def summary(numbers: list[float]) -> dict[str, Any]:
    return {
        "count": len(numbers),
        "mean": mean(numbers) if numbers else None,
        "median": median(numbers) if numbers else None,
        "p25": percentile(numbers, 0.25),
        "p75": percentile(numbers, 0.75),
    }


def bootstrap_mean_difference(a: list[float], b: list[float], samples: int, seed: int) -> dict[str, Any] | None:
    if not a or not b:
        return None
    rng = random.Random(seed)
    differences = [mean(rng.choices(b, k=len(b))) - mean(rng.choices(a, k=len(a))) for _ in range(samples)]
    return {"candidate_minus_baseline_mean": mean(b) - mean(a), "bootstrap_95": [percentile(differences, 0.025), percentile(differences, 0.975)], "resamples": samples, "seed": seed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--metric", action="append", default=[])
    parser.add_argument("--include-review", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=202708)
    args = parser.parse_args()
    profile = yaml.safe_load(args.profile.read_text(encoding="utf-8"))
    records = load_registry(args.registry)
    accepted = records if args.include_review else [record for record in records if record.get("analysis_eligible")]
    condition_profiles = profile["conditions"]
    conditions = {condition: [record for record in accepted if record.get("condition_id") == condition] for condition in condition_profiles}
    metrics = tuple(args.metric) if args.metric else DEFAULT_METRICS
    metric_results = {}
    for metric in metrics:
        summaries = {condition: summary(values(items, metric)) for condition, items in conditions.items()}
        baseline_id = next((condition for condition, definition in condition_profiles.items() if definition.get("role") == "A"), None)
        comparisons = {}
        if baseline_id is not None:
            baseline_values = values(conditions[baseline_id], metric)
            for condition, items in conditions.items():
                if condition != baseline_id:
                    comparisons[f"{condition}_minus_{baseline_id}"] = bootstrap_mean_difference(baseline_values, values(items, metric), args.bootstrap_samples, args.seed)
        metric_results[metric] = {"by_condition": summaries, "baseline_comparisons": comparisons}
    target = int(profile["design"]["pilot_valid_episodes_per_condition"])
    report = {
        "schema": "robot_teleop.ab-aggregate-report/v1",
        "registry": str(args.registry.resolve()),
        "profile": str(args.profile.resolve()),
        "experiment_id": profile.get("experiment_id"),
        "included_records": len(accepted),
        "excluded_records": len(records) - len(accepted),
        "condition_counts": {condition: {"role": condition_profiles[condition].get("role"), "count": len(items)} for condition, items in conditions.items()},
        "pilot_target_per_condition": target,
        "collection_deficit": {condition: max(0, target - len(items)) for condition, items in conditions.items()},
        "metrics": metric_results,
        "notes": [
            "This report is descriptive and uses unpaired bootstrap differences.",
            "A within-subject inferential test requires an explicit pair_id recorded for both conditions.",
            "No task-success conclusion is made until the task evaluator is attached.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "included_records": len(accepted), "condition_counts": report["condition_counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
