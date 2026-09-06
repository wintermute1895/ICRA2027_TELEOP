#!/usr/bin/env python3
"""Prepare all eligible capture runs, then train one filter round."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robot_teleop.flywheel import load_flywheel_config  # noqa: E402


def eligible_runs(data_root: Path) -> list[Path]:
    result: list[Path] = []
    for run in sorted((data_root / "evidence" / "teleop").glob("*")):
        if not run.is_dir():
            continue
        required = [
            run / "artifacts" / "rosbag2" / "metadata.yaml",
            run / "artifacts" / "teleop_capture_manifest.json",
            run / "artifacts" / "terminal_audit.json",
        ]
        events = [run / "artifacts" / "audit_events_reviewed.jsonl", run / "artifacts" / "audit_events.jsonl"]
        if not all(path.is_file() for path in required) or not any(path.is_file() for path in events):
            continue
        try:
            audit = json.loads((run / "artifacts" / "terminal_audit.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if audit.get("success") is True and audit.get("safety_violation") is False and audit.get("unlogged_external_override") is False:
            result.append(run)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/flywheel/default.yaml")
    parser.add_argument("--limit", type=int, default=0, help="process at most N runs; zero means all")
    parser.add_argument("--prepare-only", action="store_true", help="prepare eligible views without training")
    args = parser.parse_args()
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    config_path = args.config.resolve()
    config = load_flywheel_config(config_path, ROOT)
    runs = eligible_runs(config.data_root)
    if args.limit:
        runs = runs[:args.limit]
    if not runs:
        raise SystemExit(f"no eligible capture runs under {config.data_root / 'evidence/teleop'}")

    command_base = [sys.executable, str(ROOT / "tools/run_flywheel.py"), "--config", str(config_path), "--prepare-only"]
    prepared: list[str] = []
    failed: list[dict[str, str]] = []
    for run in runs:
        print(f"[PREPARE] {run.name}", flush=True)
        result = subprocess.run([*command_base, str(run)], check=False)
        if result.returncode == 0:
            prepared.append(str(run))
        else:
            failed.append({"run": str(run), "reason": f"prepare_exit_{result.returncode}"})

    training_run = None
    if prepared and not args.prepare_only:
        # Prepare every eligible episode first, then create one episode-level
        # split and train one round over the compatible views.
        result = subprocess.run([
            sys.executable, str(ROOT / "tools/run_flywheel.py"), prepared[-1],
            "--config", str(config_path),
        ], check=False)
        if result.returncode != 0:
            failed.append({"run": prepared[-1], "reason": f"training_exit_{result.returncode}"})
        else:
            training_run = "completed"

    summary = {"schema": "robot_teleop.flywheel-batch/v1", "config": str(config_path),
               "eligible": len(runs), "prepared": prepared, "failed": failed,
               "training": training_run}
    print(json.dumps(summary, indent=2))
    return 0 if prepared and not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
