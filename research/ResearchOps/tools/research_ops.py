#!/usr/bin/env python3
"""Read-only local audit and claim/experiment consistency checks for ResearchOps."""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read JSON {path}: {exc}") from exc


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def better_bibtex_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("items", [])
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [item for item in items if isinstance(item, dict) and item.get("title")]


def audit_zotero(pattern: str, output: Path) -> int:
    paths = [Path(item) for item in glob.glob(pattern)]
    if not paths:
        raise SystemExit(f"no Better BibTeX JSON matched: {pattern}")
    records: list[dict[str, Any]] = []
    bad_files: list[str] = []
    for path in paths:
        try:
            for item in better_bibtex_items(load_json(path)):
                records.append({"source": str(path), **item})
        except SystemExit:
            bad_files.append(str(path))
    title_records: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        title_records.setdefault(normalize_title(str(item.get("title", ""))), []).append(item)
    duplicates = []
    for title, items in sorted(title_records.items()):
        if not title or len(items) < 2:
            continue
        sources = sorted({item["source"] for item in items})
        duplicates.append({
            "normalized_title": title,
            "count": len(items),
            "classification": "cross_collection_overlap" if len(sources) > 1 else "within_export_duplicate",
            "citation_keys": sorted(str(item.get("citationKey", "")) for item in items),
            "sources": sources,
        })
    required = ("title", "date", "publicationTitle", "DOI", "url")
    missing = {field: sum(not item.get(field) for item in records) for field in required}
    def extract_year(item: dict[str, Any]) -> str:
        match = re.search(r"(?:19|20)\d{2}", str(item.get("date", "")))
        return match.group(0) if match else "unknown"
    years = Counter(extract_year(item) for item in records)
    report = {
        "schema": "vist.researchops.zotero-audit/v1",
        "mode": "read_only_export_audit",
        "sources": [str(path) for path in paths],
        "parsed_items": len(records),
        "bad_files": bad_files,
        "missing_field_counts": missing,
        "year_counts": dict(sorted(years.items())),
        "duplicate_title_groups": duplicates,
        "note": "Export metadata is inventory only. Verify venue/year/DOI from official sources before citing.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "items": len(records), "duplicate_groups": len(duplicates)}, ensure_ascii=False))
    return 0


def load_records(name: str) -> list[dict[str, Any]]:
    payload = load_json(ROOT / f"{name}.json")
    values = payload.get(name) if isinstance(payload, dict) else None
    if not isinstance(values, list):
        raise SystemExit(f"{name}.json must contain a list named {name}")
    return values


def validate() -> int:
    claims = load_records("claims")
    experiments = load_records("experiments")
    experiment_ids = {item.get("id") for item in experiments}
    issues: list[str] = []
    for claim in claims:
        cid = claim.get("id", "<missing>")
        for field in ("claim", "scope", "counterexample", "required_evidence", "experiment_ids", "decision_rule"):
            if not claim.get(field):
                issues.append(f"{cid}: missing {field}")
        for eid in claim.get("experiment_ids", []):
            if eid not in experiment_ids:
                issues.append(f"{cid}: unknown experiment {eid}")
    for experiment in experiments:
        eid = experiment.get("id", "<missing>")
        for field in ("hypothesis", "conditions", "primary_metrics", "data_contract", "code_hooks", "failure_criterion"):
            if not experiment.get(field):
                issues.append(f"{eid}: missing {field}")
    if issues:
        print("ResearchOps validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "pass", "claims": len(claims), "experiments": len(experiments)}))
    return 0


def check_code_paths() -> int:
    experiments = load_records("experiments")
    missing: list[str] = []
    checked = 0
    for experiment in experiments:
        for hook in experiment.get("code_hooks", []):
            checked += 1
            if not Path(hook).exists():
                missing.append(f"{experiment.get('id')}: {hook}")
    result = {"status": "pass" if not missing else "review", "checked": checked, "missing": missing,
              "note": "Existence verifies an integration hook, not semantic correctness or real-robot safety."}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


def matrix(output: Path) -> int:
    claims = load_records("claims")
    experiments = {item["id"]: item for item in load_records("experiments")}
    lines = ["# Claim-Evidence Matrix", "", "Generated from `claims.json` and `experiments.json`. Paper IDs are evidence obligations until a verified card exists.", ""]
    for claim in claims:
        lines += [f"## {claim['id']}: {claim['claim']}", "", f"- Boundary: {claim['scope']}", f"- Counterexample: {claim['counterexample']}", f"- Required paper evidence: {', '.join(claim['required_evidence'])}", f"- Decision rule: {claim['decision_rule']}", "- Experiments:"]
        for eid in claim["experiment_ids"]:
            experiment = experiments.get(eid, {})
            lines.append(f"  - `{eid}` {experiment.get('name', 'MISSING')}: primary={', '.join(experiment.get('primary_metrics', []))}; fail={experiment.get('failure_criterion', 'MISSING')}")
        lines.append("")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"matrix": str(output), "claims": len(claims)}))
    return 0


def brief(output: Path) -> int:
    claims = load_records("claims")
    pending = sorted({paper_id for claim in claims for paper_id in claim.get("required_evidence", [])
                      if paper_id.startswith("P") and not (ROOT / "papers" / f"{paper_id}.md").exists()})
    # Dated directories are produced by the curated query set. One-off ad hoc
    # result files are intentionally excluded from the recurring review queue.
    candidate_root = ROOT / "papers" / "candidates"
    candidate_files = sorted(path for path in candidate_root.rglob("*.json") if path.parent != candidate_root)
    candidates: list[dict[str, Any]] = []
    for path in candidate_files:
        try:
            payload = load_json(path)
        except SystemExit:
            continue
        candidates.extend(item for item in payload.get("candidates", []) if isinstance(item, dict))
    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = normalize_title(str(item.get("title", "")))
        if key and key not in unique:
            unique[key] = item
    selected = sorted(unique.values(), key=lambda item: (not item.get("venue_allowlist_match", False), -(item.get("cited_by_count") or 0)))[:15]
    lines = ["# ResearchOps Brief", "", "This is a review queue, not a literature claim.", "", "## Claims blocked on verified paper cards", ""]
    lines += [f"- `{item}`: create `papers/{item}.md` after checking an official source and full text." for item in pending] or ["- None"]
    lines += ["", "## Candidate review queue", "", "Candidates may be irrelevant or metadata-incomplete. Verify before citation.", ""]
    for item in selected:
        source = item.get("doi") or item.get("landing_page") or item.get("open_access_url") or "no link"
        lines.append(f"- {'[top-venue lead]' if item.get('venue_allowlist_match') else '[lead]'} {item.get('publication_date')} | {item.get('venue') or 'venue missing'} | {item.get('title')} | {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"brief": str(output), "pending_paper_cards": len(pending), "unique_candidates": len(unique)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-zotero")
    audit.add_argument("--input", required=True, help="glob pattern for Better BibTeX JSON exports")
    audit.add_argument("--output", type=Path, required=True)
    sub.add_parser("validate")
    sub.add_parser("check-code-paths")
    matrix_parser = sub.add_parser("matrix")
    matrix_parser.add_argument("--output", type=Path, required=True)
    brief_parser = sub.add_parser("brief")
    brief_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit-zotero":
        return audit_zotero(args.input, args.output)
    if args.command == "validate":
        return validate()
    if args.command == "check-code-paths":
        return check_code_paths()
    if args.command == "brief":
        return brief(args.output)
    return matrix(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
