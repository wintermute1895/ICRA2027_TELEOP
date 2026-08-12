#!/usr/bin/env python3
"""Build a read-only canonical episode registry from derived analysis reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def infer_arm(report: dict[str, Any]) -> str | None:
    arm = report.get("arm")
    if arm in {"left", "right"}:
        return arm
    source = str(report.get("source_episode", "")).lower()
    name = Path(source).name
    if name.startswith("left_") or "_left_" in name:
        return "left"
    if name.startswith("right_") or "_right_" in name:
        return "right"
    return None


def load_reports(roots: list[Path]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    categories = {
        "robot_teleop.episode-data-quality-report/v1": "data_quality",
        "robot_teleop.trajectory-quality-report/v1": "trajectory",
        "robot_teleop.hard-case-report/v1": "hard_cases",
    }
    for root in roots:
        for path in root.rglob("*.json"):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(report, dict) or not isinstance(report.get("schema"), str):
                continue
            schema = report["schema"]
            if schema not in categories:
                continue
            episode_id = report.get("episode_id")
            arm = infer_arm(report)
            if not isinstance(episode_id, str) or arm not in {"left", "right"}:
                continue
            key = f"{episode_id}:{arm}"
            category = categories[schema]
            grouped.setdefault(key, {})[category] = {"path": str(path.resolve()), "report": report}
    return grouped


def capture_metadata(report_path: Path, roots: list[Path]) -> dict[str, Any]:
    for parent in (report_path, *report_path.parents):
        if not any(parent == root or root in parent.parents for root in roots):
            continue
        candidate = parent / "artifacts" / "teleop_capture_manifest.json"
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8")).get("experiment", {})
            except (OSError, json.JSONDecodeError):
                return {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, action="append", required=True, help="directory containing reports; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    roots = [path.resolve() for path in args.root if path.is_dir()]
    if not roots:
        raise SystemExit("no --root directory exists")
    grouped = load_reports(roots)
    records = []
    for key, reports in sorted(grouped.items()):
        quality = reports.get("data_quality")
        trajectory = reports.get("trajectory")
        hard_cases = reports.get("hard_cases")
        primary = (quality or trajectory or hard_cases)["report"]
        primary_path = Path((quality or trajectory or hard_cases)["path"])
        experiment = capture_metadata(primary_path, roots)
        metrics = (trajectory or {}).get("report", {}).get("metrics", {})
        quality_gate = (quality or {}).get("report", {}).get("quality_gate", "missing")
        trajectory_gate = (trajectory or {}).get("report", {}).get("trajectory_quality_gate", "missing")
        records.append({
            "schema": "robot_teleop.episode-registry-record/v1",
            "registry_key": key,
            "episode_id": primary.get("episode_id"),
            "arm": primary.get("arm"),
            "source_domain": primary.get("source_domain"),
            "experiment_id": experiment.get("experiment_id", "unassigned"),
            "condition_id": experiment.get("condition_id", "unassigned"),
            "operator_id": experiment.get("operator_id", "anonymous"),
            "task_id": experiment.get("task_id", "unspecified"),
            "data_quality_gate": quality_gate,
            "data_quality_score": (quality or {}).get("report", {}).get("data_quality_score"),
            "trajectory_quality_gate": trajectory_gate,
            "tracking_error_rms_rad": metrics.get("tracking_error_rad", {}).get("rms"),
            "tracking_error_p95_rad": metrics.get("tracking_error_rad", {}).get("p95"),
            "jerk_rms_rad_s3": metrics.get("jerk_rad_s3", {}).get("rms"),
            "minimum_singular_value": metrics.get("minimum_singular_value", {}).get("minimum"),
            "minimum_clearance_m": metrics.get("minimum_clearance_m", {}).get("minimum"),
            "hard_case_count": (hard_cases or {}).get("report", {}).get("hard_case_count", 0),
            "analysis_eligible": quality_gate == "pass" and trajectory_gate == "pass",
            "reports": {name: item["path"] for name, item in reports.items()},
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    summary = {
        "schema": "robot_teleop.episode-registry-summary/v1",
        "roots": [str(root) for root in roots],
        "record_count": len(records),
        "analysis_eligible_count": sum(record["analysis_eligible"] for record in records),
    }
    args.output.with_suffix(args.output.suffix + ".summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **summary}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
