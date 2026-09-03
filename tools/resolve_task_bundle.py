#!/usr/bin/env python3
"""Resolve and validate one versioned task bundle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from robot_teleop.task_config import load_task_bundle, resolve_registered_task  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path)
    parser.add_argument("--task-id")
    parser.add_argument("--registry", type=Path, default=Path("config/tasks/registry.yaml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if bool(args.task) == bool(args.task_id):
            raise ValueError("provide exactly one of --task or --task-id")
        bundle, _ = load_task_bundle(args.task) if args.task else resolve_registered_task(args.task_id, args.registry)
    except (OSError, ValueError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
