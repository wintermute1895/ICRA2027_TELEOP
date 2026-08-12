#!/usr/bin/env python3
"""Remote worker contract for optional visual/collision mesh generation.

The worker is intentionally conservative: it never claims a mesh is licensed.
It requires an input asset and an explicit manifest, and leaves the primitive
MuJoCo baseline untouched when optional tooling is unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input asset not found: {args.input}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    required = ("source_url", "license", "attribution", "scale_to_meters", "used_for")
    missing = [key for key in required if key not in manifest]
    if missing:
        raise SystemExit("manifest missing: " + ", ".join(missing))
    if manifest["used_for"] != "visual_only":
        raise SystemExit("optional downloaded meshes must be visual_only")
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / args.input.name
    shutil.copy2(args.input, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest.update({"retrieved_at": manifest.get("retrieved_at", datetime.now(timezone.utc).isoformat()), "sha256": digest})
    (args.output / (destination.stem + ".manifest.json")).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"visual_asset": str(destination), "sha256": digest, "passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
