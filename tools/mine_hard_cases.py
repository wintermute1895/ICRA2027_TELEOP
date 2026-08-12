#!/usr/bin/env python3
"""Read-only hard-case mining from one trajectory-quality report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/experiments/hard_case_mining.yaml"


def exceeds(value: Any, threshold: float, lower_is_worse: bool = False) -> bool:
    if not isinstance(value, (int, float)):
        return False
    return float(value) < threshold if lower_is_worse else float(value) > threshold


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    report = json.loads(args.trajectory_report.read_text(encoding="utf-8"))
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    thresholds = config["thresholds"]
    maximum_gap = int(config["grouping"]["maximum_clean_gap_samples"])
    minimum_samples = int(config["grouping"]["minimum_segment_samples"])
    flagged: list[dict[str, Any]] = []
    for sample in report.get("sample_metrics", []):
        reasons = []
        if exceeds(sample.get("tracking_error_max_rad"), thresholds["tracking_error_rad"]): reasons.append("tracking_error")
        if exceeds(sample.get("velocity_max_rad_s"), thresholds["velocity_rad_s"]): reasons.append("velocity")
        if exceeds(sample.get("acceleration_max_rad_s2"), thresholds["acceleration_rad_s2"]): reasons.append("acceleration")
        if exceeds(sample.get("jerk_max_rad_s3"), thresholds["jerk_rad_s3"]): reasons.append("jerk")
        if exceeds(sample.get("minimum_singular_value"), thresholds["minimum_singular_value"], lower_is_worse=True): reasons.append("singularity")
        if exceeds(sample.get("minimum_clearance_m"), thresholds["minimum_clearance_m"], lower_is_worse=True): reasons.append("clearance")
        if reasons:
            flagged.append({**sample, "reasons": reasons})
    segments: list[dict[str, Any]] = []
    for sample in flagged:
        if not segments or sample["sample_index"] > segments[-1]["end_sample_index"] + maximum_gap + 1:
            segments.append({"start_sample_index": sample["sample_index"], "end_sample_index": sample["sample_index"], "reasons": set(sample["reasons"]), "samples": [sample]})
        else:
            segment = segments[-1]
            segment["end_sample_index"] = sample["sample_index"]
            segment["reasons"].update(sample["reasons"])
            segment["samples"].append(sample)
    result_segments = []
    for segment in segments:
        if len(segment["samples"]) < minimum_samples:
            continue
        result_segments.append({
            "start_sample_index": segment["start_sample_index"],
            "end_sample_index": segment["end_sample_index"],
            "reasons": sorted(segment["reasons"]),
            "flagged_sample_count": len(segment["samples"]),
            "peak_tracking_error_rad": max((item["tracking_error_max_rad"] or 0.0 for item in segment["samples"])),
            "peak_jerk_rad_s3": max((item["jerk_max_rad_s3"] or 0.0 for item in segment["samples"])),
            "minimum_singular_value": min((item["minimum_singular_value"] for item in segment["samples"] if item["minimum_singular_value"] is not None), default=None),
            "minimum_clearance_m": min((item["minimum_clearance_m"] for item in segment["samples"] if item["minimum_clearance_m"] is not None), default=None),
        })
    output = {
        "schema": "robot_teleop.hard-case-report/v1",
        "evaluation_mode": "offline_read_only",
        "hardware_accessed": False,
        "trajectory_report": str(args.trajectory_report.resolve()),
        "episode_id": report.get("episode_id"),
        "source_domain": report.get("source_domain"),
        "arm": report.get("arm"),
        "hard_case_count": len(result_segments),
        "segments": result_segments,
        "notes": ["Segments are data-prioritization targets. They are not autonomous recovery commands."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "hard_case_count": len(result_segments)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
