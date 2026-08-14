#!/usr/bin/env python3
"""Fetch recent paper candidates from OpenAlex. Results are never imported into Zotero."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path


VENUES = {
    "ICRA", "IROS", "Robotics: Science and Systems", "Robotics and Automation Letters",
    "IEEE Transactions on Robotics", "The International Journal of Robotics Research",
    "Conference on Robot Learning", "Science Robotics", "Nature Machine Intelligence",
    "NeurIPS", "International Conference on Learning Representations", "International Conference on Machine Learning",
}


def venue_name(work: dict) -> str | None:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    return source.get("display_name")


def venue_allowlist_match(work: dict, venue: str | None) -> bool:
    if venue in VENUES:
        return True
    # OpenAlex often exposes RSS papers only through their DOI, without a source.
    doi = (work.get("doi") or "").lower()
    return doi.startswith("https://doi.org/10.15607/rss.")


def authors(work: dict) -> list[str]:
    return [entry.get("author", {}).get("display_name", "") for entry in work.get("authorships", []) if entry.get("author", {}).get("display_name")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--from-year", type=int, default=date.today().year - 3)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--title-include", nargs="*", default=[], help="keep candidates whose title contains at least one supplied term")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.per_page <= 200:
        raise SystemExit("--per-page must be in 1..200")
    params = urllib.parse.urlencode({
        "search": args.query,
        "filter": f"from_publication_date:{args.from_year}-01-01,to_publication_date:{date.today().isoformat()}",
        "per-page": args.per_page,
        "sort": "cited_by_count:desc",
    })
    request = urllib.request.Request(f"https://api.openalex.org/works?{params}", headers={"User-Agent": "VIST-ResearchOps/1.0 (local literature candidate search)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    candidates = []
    title_terms = [term.lower() for term in args.title_include if term.strip()]
    for work in payload.get("results", []):
        venue = venue_name(work)
        title = work.get("title") or ""
        if title_terms and not any(term in title.lower() for term in title_terms):
            continue
        candidates.append({
            "openalex_id": work.get("id"),
            "title": title,
            "publication_date": work.get("publication_date"),
            "venue": venue,
            "venue_allowlist_match": venue_allowlist_match(work, venue),
            "doi": work.get("doi"),
            "open_access_url": (work.get("open_access") or {}).get("oa_url"),
            "landing_page": (work.get("primary_location") or {}).get("landing_page_url"),
            "authors": authors(work),
            "cited_by_count": work.get("cited_by_count"),
            "verification_status": "candidate_not_citable_until_primary_source_checked",
        })
    result = {
        "schema": "vist.researchops.paper-candidates/v1",
        "source": "OpenAlex",
        "query": args.query,
        "from_year": args.from_year,
        "title_include": title_terms,
        "retrieved_on": date.today().isoformat(),
        "candidates": candidates,
        "required_next_step": "Verify official venue/year/DOI and inspect full text before creating a paper evidence card or using as claim evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "candidates": len(candidates), "allowlist_matches": sum(item["venue_allowlist_match"] for item in candidates)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
