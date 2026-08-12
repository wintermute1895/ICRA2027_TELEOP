#!/usr/bin/env python3
"""Read-only data-quality gate for canonical simulation or real episode JSONL."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/experiments/data_quality_gate.yaml"


def finite_vector(value: Any, length: int) -> bool:
    return isinstance(value, list) and len(value) == length and all(
        isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value
    )


def coverage(records: list[dict[str, Any]], key: str, valid) -> float:
    return sum(bool(valid(record.get(key))) for record in records) / len(records)


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise SystemExit(f"record at {path}:{line_number} is not an object")
        records.append(record)
    if not records:
        raise SystemExit(f"episode is empty: {path}")
    return records


def evaluate(records: list[dict[str, Any]], config: dict[str, Any], source: Path) -> dict[str, Any]:
    thresholds = config["thresholds"]
    requirements = config["requirements"]
    required_fields = config["required_fields"]
    joint_count = len(records[0].get("joint_names", []))
    timestamps = [record.get("header_stamp_ns") for record in records]
    timestamp_valid = all(isinstance(value, int) for value in timestamps)
    periods_ms = (
        [(right - left) / 1e6 for left, right in zip(timestamps, timestamps[1:])]
        if timestamp_valid else []
    )
    required_coverage = {
        key: sum(key in record and record[key] is not None for record in records) / len(records)
        for key in required_fields
    }
    state_coverage = coverage(records, "robot_joint_state_rad", lambda value: finite_vector(value, joint_count))
    command_coverage = coverage(records, "mapped_joint_command_rad", lambda value: finite_vector(value, joint_count))
    rgb_coverage = coverage(records, "rgb", lambda value: value is not None)
    depth_coverage = coverage(records, "depth", lambda value: value is not None)
    strictly_increasing = bool(periods_ms) and all(period > 0.0 for period in periods_ms)
    max_gap_ms = max(periods_ms) if periods_ms else None

    checks = {
        "minimum_samples": len(records) >= int(config["minimum_samples"]),
        "required_fields": all(value == 1.0 for value in required_coverage.values()),
        "state_coverage": state_coverage >= float(thresholds["state_coverage_min"]),
        "command_coverage": command_coverage >= float(thresholds["command_coverage_min"]),
        "timestamps": (not requirements["require_strictly_increasing_timestamps"] or strictly_increasing),
        "maximum_gap": max_gap_ms is not None and max_gap_ms <= float(thresholds["maximum_gap_ms"]),
        "rgb_coverage": (not requirements["require_rgb"] or rgb_coverage >= float(thresholds["rgb_coverage_min"])),
        "depth_coverage": (not requirements["require_depth"] or depth_coverage >= float(thresholds["depth_coverage_min"])),
    }
    scored_components = [state_coverage, command_coverage, float(checks["timestamps"]), float(checks["maximum_gap"])]
    if requirements["require_rgb"]:
        scored_components.append(rgb_coverage)
    if requirements["require_depth"]:
        scored_components.append(depth_coverage)
    score = sum(scored_components) / len(scored_components)
    failure_reasons = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "robot_teleop.episode-data-quality-report/v1",
        "evaluation_mode": "offline_read_only",
        "hardware_accessed": False,
        "source_episode": str(source.resolve()),
        "source_domain": records[0].get("source_domain"),
        "episode_id": records[0].get("episode_id"),
        "arm": records[0].get("arm"),
        "sample_count": len(records),
        "joint_count": joint_count,
        "data_quality_score": score,
        "coverage": {
            "required_fields": required_coverage,
            "robot_joint_state": state_coverage,
            "mapped_joint_command": command_coverage,
            "rgb": rgb_coverage,
            "depth": depth_coverage,
        },
        "timing": {
            "strictly_increasing": strictly_increasing,
            "median_period_ms": median(periods_ms) if periods_ms else None,
            "maximum_gap_ms": max_gap_ms,
        },
        "checks": checks,
        "quality_gate": "pass" if not failure_reasons else "review",
        "failure_reasons": failure_reasons,
        "notes": [
            "This gate determines analysis eligibility, not task success or A/B condition.",
            "Collision, joint limits, singularity, and task success require separate evaluators.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    report = evaluate(load_records(args.episode), config, args.episode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "quality_gate": report["quality_gate"], "score": report["data_quality_score"]}))
    return 0 if report["quality_gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
