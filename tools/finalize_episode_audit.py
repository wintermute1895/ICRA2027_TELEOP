#!/usr/bin/env python3
"""Create an explicit, immutable terminal audit for one teleoperation episode."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    outcome = parser.add_mutually_exclusive_group(required=True)
    outcome.add_argument("--success", action="store_true")
    outcome.add_argument("--failure", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--termination-reason", required=True)
    parser.add_argument("--operator-id", default="anonymous")
    parser.add_argument("--safety-violation", action="store_true")
    parser.add_argument("--unlogged-external-override", action="store_true")
    parser.add_argument("--evidence-ref", action="append", default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite audit: {args.output}")
    payload = {
        "schema": "robot_teleop.terminal-audit/v0.1", "episode_id": args.episode_id,
        "success": bool(args.success), "termination_reason": args.termination_reason,
        "safety_violation": bool(args.safety_violation),
        "unlogged_external_override": bool(args.unlogged_external_override),
        "audit_source": "manual_structured", "operator_id": args.operator_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "evidence_refs": args.evidence_ref,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "episode_id": args.episode_id, "success": payload["success"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
