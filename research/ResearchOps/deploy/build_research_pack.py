#!/usr/bin/env python3
"""Build a compact, immutable ResearchOps distribution pack without Zotero SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


OBSIDIAN = Path("/mnt/F/Obsidian")
RESEARCH = OBSIDIAN / "Vault" / "ResearchOps"


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"output already exists: {output}")
    output.mkdir(parents=True)
    for name in ("README.md", "research_goal.md", "claims.json", "experiments.json", "code_interfaces.json", "queries.json", "legacy_data_plan.md", "literature_review_20260719.md"):
        copy(RESEARCH / name, output / "ResearchOps" / name)
    for relative in ("tools", "scripts", "templates", "config", "papers"):
        shutil.copytree(RESEARCH / relative, output / "ResearchOps" / relative, ignore=shutil.ignore_patterns("__pycache__", ".gitkeep"))
    # Only portable exports, never a live Zotero database nor broad attachment storage.
    exports = [
        OBSIDIAN / "Zotero" / "VIST_ICRA2027_papers_20260719.bib",
        OBSIDIAN / "Zotero" / "VIST_papers_2026.bib",
        OBSIDIAN / "Zotero" / "better-bibtex" / "My Library-VIST.json",
        OBSIDIAN / "Zotero" / "better-bibtex" / "My Library-VIST-Baselines & SOTA.json",
        OBSIDIAN / "Zotero" / "better-bibtex" / "My Library-VIST-Data Quality & Learning.json",
        OBSIDIAN / "Zotero" / "better-bibtex" / "My Library-Robotics_Teleop_Diffusion-01_Teleop_Systems.json",
    ]
    for source in exports:
        copy(source, output / "literature" / "exports" / source.name)
    notes = [
        OBSIDIAN / "Vault" / "Learning" / "灵巧手语义遥操作-文献地图.md",
        OBSIDIAN / "Vault" / "Learning" / "文献阅读指南.md",
    ]
    for source in notes:
        copy(source, output / "literature" / "notes" / source.name)
    pdfs = [
        OBSIDIAN / "Zotero" / "storage" / "DGN5M78F" / "Si 等 - 2024 - Tilde Teleoperation for Dexterous In-Hand Manipulation Learning with a DeltaHand.pdf",
        OBSIDIAN / "Zotero" / "storage" / "8WJLRQ4W" / "Wang 等 - 2024 - DexCap Scalable and Portable Mocap Data Collection System for Dexterous Manipulation.pdf",
        OBSIDIAN / "Zotero" / "storage" / "P2KVWQB7" / "Güleçyüz 等 - 2025 - Enhancing Shared Autonomy in Teleoperation Under Network Delay Transparency- and Confidence-Aware A.pdf",
        OBSIDIAN / "Zotero" / "storage" / "5IJRK09B" / "Liu_等_-_2026_-_SUBTA.pdf",
        OBSIDIAN / "Zotero" / "storage" / "3EZTO9VA" / "Liu_等_-_2026_-_Adaptor.pdf",
        OBSIDIAN / "Zotero" / "storage" / "X6PTED09" / "Kulkarni_等_-_2026_-_RINSE.pdf",
        OBSIDIAN / "Zotero" / "storage" / "ICFLDR5D" / "Zhou_等_-_2026_-_SAPS.pdf",
        OBSIDIAN / "Zotero" / "storage" / "MZPIJ12K" / "Jabbour_等_-_2024_-_MPC_Blending.pdf",
    ]
    for source in pdfs:
        copy(source, output / "literature" / "pdf" / source.name)
    readme = output / "README.md"
    readme.write_text(
        "# VIST Research Pack\n\n"
        "Portable, read-only research package generated from ilex22. It intentionally excludes Zotero SQLite and generic attachment storage.\n\n"
        "Core reading order: `Tilde` (DAgger-style corrective data collection), `DexCap` (collection system + interactive correction), then `What Matters in Learning from Offline Human Demonstrations` (metadata only; obtain and verify the full text before citation).\n\n"
        "The code paths in `ResearchOps/code_interfaces.json` point to ilex22 and are documentary on other machines. The portable literature and research workflow can run independently; robot-specific analysis remains on ilex22 unless those repositories are separately cloned.\n",
        encoding="utf-8",
    )
    files = sorted(path for path in output.rglob("*") if path.is_file())
    manifest = {
        "schema": "vist.researchops.portable-pack/v1",
        "generated_from": str(RESEARCH),
        "files": [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
        "excluded": ["Zotero/zotero.sqlite", "Zotero/storage except selected PDFs", "raw historical datasets", "ROS2 workspaces"],
    }
    (output / "PACK_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "files": len(files), "bytes": sum(item["bytes"] for item in manifest["files"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
