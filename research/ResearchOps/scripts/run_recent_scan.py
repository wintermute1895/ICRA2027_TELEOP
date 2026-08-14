#!/usr/bin/env python3
"""Run the curated ResearchOps query set and write dated candidate JSON files."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "tools" / "search_openalex.py"


def main() -> int:
    queries = json.loads((ROOT / "queries.json").read_text(encoding="utf-8"))
    output_dir = ROOT / "papers" / "candidates" / date.today().isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    for item in queries["queries"]:
        output = output_dir / f"{item['id'].lower()}.json"
        command = [sys.executable, str(SEARCH), "--query", item["query"], "--from-year", str(queries["from_year"]), "--output", str(output)]
        if item.get("title_include"):
            command += ["--title-include", *item["title_include"]]
        print("Running", item["id"], flush=True)
        result = subprocess.run(command, check=False)
        if result.returncode:
            failures.append(item["id"])
    manifest = {"schema": "vist.researchops.scan-manifest/v1", "date": date.today().isoformat(),
                "query_set": "queries.json", "output_dir": str(output_dir), "failed_queries": failures,
                "next_step": "Review candidates against official sources; do not cite or import automatically."}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
