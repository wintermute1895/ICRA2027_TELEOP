#!/usr/bin/env python3
"""Read-only inventory for legacy robot-teleoperation datasets.

The scanner reads small metadata files and filesystem stat information. It does
not open ROS bags, decode images/video, or modify the source disk.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required for metadata inventory") from exc


def read_yaml(path: Path) -> dict[str, Any] | None:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, yaml.YAMLError):
        return None
    return value if isinstance(value, dict) else None


def file_summary(root: Path) -> tuple[int, int, Counter[str]]:
    count = 0
    size = 0
    extensions: Counter[str] = Counter()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        try:
            size += path.stat().st_size
        except OSError:
            continue
        extensions[path.suffix.lower() or "<none>"] += 1
    return count, size, extensions


def experiment_records(root: Path) -> list[dict[str, Any]]:
    records = []
    for metadata_path in sorted(root.rglob("experiment_metadata.yaml")):
        metadata = read_yaml(metadata_path) or {}
        bag_metadata = read_yaml(metadata_path.parent / "metadata.yaml") or {}
        experiment = metadata.get("experiment") or {}
        rosbag = bag_metadata.get("rosbag2_bagfile_information") or {}
        topics = rosbag.get("topics_with_message_count") or []
        topic_counts = {}
        for entry in topics:
            item = entry.get("topic_metadata") if isinstance(entry, dict) else None
            if not isinstance(item, dict) or not item.get("name"):
                continue
            topic_counts[item["name"]] = entry.get("message_count")
        records.append({
            "path": str(metadata_path.parent),
            "experiment_name": experiment.get("name"),
            "timestamp": experiment.get("timestamp"),
            "duration": experiment.get("duration"),
            "components": metadata.get("components", []),
            "recording_mode": (metadata.get("config") or {}).get("recording_mode", {}).get("mode"),
            "message_count": rosbag.get("message_count"),
            "duration_ns": rosbag.get("duration", {}).get("nanoseconds"),
            "starting_time_ns": rosbag.get("starting_time", {}).get("nanoseconds_since_epoch"),
            "topics": topic_counts,
            "has_intent_factors": (metadata_path.parent / "intent_factors_timeseries.json").exists(),
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_dir():
        raise SystemExit(f"dataset root is not a directory: {args.root}")

    groups = []
    all_records = []
    for group in sorted(path for path in args.root.iterdir() if path.is_dir()):
        count, size, extensions = file_summary(group)
        records = experiment_records(group)
        all_records.extend(records)
        groups.append({
            "name": group.name,
            "path": str(group),
            "file_count": count,
            "size_bytes": size,
            "size_gib": round(size / 1024**3, 3),
            "extensions": dict(sorted(extensions.items())),
            "experiment_count": len(records),
            "rosbag_count": sum(1 for path in group.rglob("*.db3") if path.is_file()),
            "video_count": sum(1 for suffix in ("*.mp4", "*.avi", "*.mkv") for path in group.rglob(suffix) if path.is_file()),
            "numpy_count": sum(1 for suffix in ("*.npy", "*.npz") for path in group.rglob(suffix) if path.is_file()),
        })

    topic_counts: Counter[str] = Counter()
    for record in all_records:
        topic_counts.update(record["topics"])
    report = {
        "schema": "vist.researchops.legacy-dataset-audit/v1",
        "mode": "read_only_metadata_and_stat_inventory",
        "root": str(args.root.resolve()),
        "groups": groups,
        "experiment_count": len(all_records),
        "experiments_with_intent_factors": sum(record["has_intent_factors"] for record in all_records),
        "topic_presence_across_experiments": dict(topic_counts),
        "sample_experiments": all_records[:20],
        "eligibility_policy": {
            "exploratory_replay": "allowed after schema/topic audit",
            "pretraining_or_warm_start": "allowed only after unit, joint order, coordinate frame and split policy are recorded",
            "confirmatory_ab": "blocked until task, condition, success label, reference revision and protocol are verified",
        },
        "note": "This report does not decode ROS bags or validate semantic equivalence with current hardware.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "groups": len(groups), "experiments": len(all_records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
