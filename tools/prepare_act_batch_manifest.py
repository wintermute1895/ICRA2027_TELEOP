#!/usr/bin/env python3
"""Create an immutable ACT batch manifest from reviewed capture evidence.

This stage is ROS-independent; bag decoding and image inspection happen later
in the ROS training environment. Raw evidence is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("evidence/teleop"))
    parser.add_argument("--prefix", default="20260901")
    parser.add_argument("--failed", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260902)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite: {args.output}")
    candidates = []
    quarantined = []
    for run in sorted(args.root.glob(f"{args.prefix}*")):
        artifacts = run / "artifacts"
        manifest = artifacts / "teleop_capture_manifest.json"
        audit = artifacts / "terminal_audit_reviewed.json"
        validation = artifacts / "capture_validation.json"
        bag = artifacts / "rosbag2"
        if not (manifest.is_file() and audit.is_file() and validation.is_file() and bag.is_dir()):
            continue
        md, ad, vd = json.loads(manifest.read_text()), json.loads(audit.read_text()), json.loads(validation.read_text())
        item = {
            "episode_id": run.name,
            "run_dir": str(run.resolve()),
            "task_id": md.get("experiment", {}).get("task_id"),
            "task_revision": md.get("experiment", {}).get("task_revision"),
            "source_bag": str(bag.resolve()),
            "terminal_audit": str(audit.resolve()),
            "capture_validation": str(validation.resolve()),
            "audit_success": ad.get("success") is True,
            "capture_validation_passed": vd.get("passed") is True,
            "failure_reason": ad.get("termination_reason"),
            "source_hashes": {"manifest": sha256(manifest), "audit": sha256(audit), "validation": sha256(validation)},
        }
        if item["audit_success"] and item["capture_validation_passed"] and run.name != args.failed:
            candidates.append(item)
        else:
            item["quarantine_reason"] = "reviewed_failure" if run.name == args.failed else "audit_or_capture_gate_failed"
            quarantined.append(item)
    if not candidates:
        raise SystemExit("no admitted episodes")
    rng = random.Random(args.seed)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    validation_count = max(1, round(len(shuffled) * args.validation_fraction)) if len(shuffled) > 1 else 0
    validation = shuffled[:validation_count]
    train = shuffled[validation_count:]
    payload = {
        "schema": "robot_teleop.act-batch-manifest/v0.1",
        "selection_policy": "reviewed_success_and_capture_validation_passed",
        "seed": args.seed,
        "validation_fraction": args.validation_fraction,
        "timestamp_policy": "ROS header timestamps; no row-index alignment",
        "camera_policy": {"required": ["main_rgb", "auxiliary_rgb"], "max_age_ms": 100.0, "black_frame_gate": "required_at_decode"},
        "train": train,
        "validation": validation,
        "quarantine": quarantined,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "train": len(train), "validation": len(validation), "quarantine": len(quarantined)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
