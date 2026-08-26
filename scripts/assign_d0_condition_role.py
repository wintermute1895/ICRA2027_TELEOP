#!/usr/bin/env python3
"""Assign the A/B role A to D0 episodes 100-139 without changing their condition name."""
from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


DATA_ROOT = Path("/media/pao/Seagate Hub/ICRA2027_TELEOP_BAGS")
BACKUP_ROOT = Path("reports/d0_first_condition_a_role_manifest_backup_20260826")
EPISODE_IDS = [f"d0_right_hand_{number}" for number in range(100, 140)]


def main() -> int:
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifests = [DATA_ROOT / episode_id / "recording_manifest.json" for episode_id in EPISODE_IDS]
    missing = [str(path) for path in manifests if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing manifests:\n" + "\n".join(missing))
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    for manifest in manifests:
        backup = BACKUP_ROOT / manifest.parent.name / manifest.name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, backup)
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["condition_role"] = "A"
        record["condition_role_label_source"] = "user"
        record["condition_role_labeled_utc"] = timestamp
        temporary = manifest.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest)
    print(json.dumps({"condition_id": "第一条件", "condition_role": "A", "episode_count": len(manifests), "backup_root": str(BACKUP_ROOT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
