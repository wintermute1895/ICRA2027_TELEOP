#!/usr/bin/env python3
"""Mark D0 right-hand episodes 100-139 as user-labeled successes."""
from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


DATA_ROOT = Path("/media/pao/Seagate Hub/ICRA2027_TELEOP_BAGS")
BACKUP_ROOT = Path("reports/d0_success_manifest_backup_20260826")
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

    for manifest in manifests:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        record["outcome"] = {
            "status": "success",
            "label_source": "user",
            "labeled_utc": timestamp,
        }
        temporary = manifest.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest)

    print(json.dumps({"marked_success": len(manifests), "backup_root": str(BACKUP_ROOT), "labeled_utc": timestamp}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
