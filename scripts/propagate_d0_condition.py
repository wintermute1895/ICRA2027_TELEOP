#!/usr/bin/env python3
"""Apply a condition ID to already-derived cleaned D0 artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleaned-root", type=Path, required=True)
    parser.add_argument("--condition-id", required=True)
    parser.add_argument("--condition-role")
    args = parser.parse_args()
    root = args.cleaned_root.resolve()
    audit_paths = sorted((root / "audits").glob("d0_right_hand_*.json"))
    cleaned_paths = sorted((root / "episodes").glob("d0_right_hand_*.jsonl"))
    for path in audit_paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        record["condition_id"] = args.condition_id
        if args.condition_role:
            record["condition_role"] = args.condition_role
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in cleaned_paths:
        temporary = path.with_suffix(".jsonl.tmp")
        with path.open("r", encoding="utf-8") as source, temporary.open("w", encoding="utf-8") as destination:
            for line in source:
                if line.strip():
                    record = json.loads(line)
                    record["condition_id"] = args.condition_id
                    if args.condition_role:
                        record["condition_role"] = args.condition_role
                    destination.write(json.dumps(record, ensure_ascii=False) + "\n")
        temporary.replace(path)
    print(json.dumps({"condition_id": args.condition_id, "condition_role": args.condition_role, "audit_count": len(audit_paths), "cleaned_episode_count": len(cleaned_paths)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
