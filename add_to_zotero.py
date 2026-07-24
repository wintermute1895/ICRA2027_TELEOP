#!/usr/bin/env python3
"""
Add papers to Zotero library — supports two modes:

  FULL-AUTO (direct):
    python add_to_zotero.py --papers papers.json --mode direct
    Writes directly to Zotero SQLite. Only safe when Zotero is RUNNING.
    May not survive Zotero restart. Fast, no user action needed.

  SEMI-AUTO (bibtex):
    python add_to_zotero.py --papers papers.json --mode bibtex
    Generates a .bib file. Import via Zotero: File -> Import (Ctrl+Shift+I).
    Reliable, survives restart, deduplicates automatically.

  AUTO (default):
    python add_to_zotero.py --papers papers.json --mode auto
    If Zotero is running → direct mode. Otherwise → bibtex mode.

Paper JSON format:
[
  {
    "title": "...",
    "authors": [["First", "Last"], ...],
    "date": "2026",
    "publicationTitle": "arXiv preprint",
    "url": "https://...",
    "doi": "10.xxx/...",
    "abstractNote": "...",
    "extra": "arXiv: XXXX.XXXXX",
    "collections": ["02_Intent_and_Context_Awareness"],
    "itemType": "journalArticle"   // or "conferencePaper", "preprint", "thesis"
  }
]
"""

import sqlite3
import json
import shutil
import os
import sys
import random
import string
import argparse
import subprocess
from datetime import datetime, timezone, timedelta


# ─── BibTeX helpers ──────────────────────────────────────────────────────────

def latex_escape(text: str) -> str:
    """Escape special characters for BibTeX."""
    if not text:
        return text
    replacements = {
        "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
        "^": r"\^{}", "\\": r"\textbackslash{}",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Handle Unicode characters that BibTeX can't handle
    text = text.replace("ş", r"{\c{s}}")  # ş
    text = text.replace("Ş", r"{\c{S}}")  # Ş
    text = text.replace("ü", r"{\"u}")    # ü
    text = text.replace("Ü", r"{\"U}")    # Ü
    text = text.replace("ç", r"{\c{c}}")  # ç
    text = text.replace("Ç", r"{\c{C}}")  # Ç
    return text


def generate_cite_key(paper: dict) -> str:
    """Generate a BibTeX citation key: firstAuthorYearFirstWord."""
    authors = paper.get("authors", [])
    if authors:
        last = authors[0][1] if len(authors[0]) > 1 else authors[0][0]
        last = last.lower().replace(" ", "_")
    else:
        last = "unknown"
    year = paper.get("date", "????")[:4]
    title = paper.get("title", "untitled")
    first_word = title.split()[0].lower().rstrip(".,;:!?")
    for char in "{}():/\\":
        first_word = first_word.replace(char, "")
    return f"{last}{year}{first_word}"


def paper_to_bibtex(paper: dict) -> str:
    """Convert a paper dict to a BibTeX entry string."""
    cite_key = paper.get("citationKey") or generate_cite_key(paper)
    item_type = paper.get("itemType", "journalArticle")

    type_map = {
        "journalArticle": "article",
        "conferencePaper": "inproceedings",
        "preprint": "article",
        "thesis": "phdthesis",
        "book": "book",
        "bookSection": "inbook",
        "report": "techreport",
        "webpage": "misc",
    }
    entry_type = type_map.get(item_type, "article")

    lines = [f"@{entry_type}{{{cite_key},"]

    title = paper.get("title", "")
    if title:
        lines.append(f"  title = {{{latex_escape(title)}}},")

    authors = paper.get("authors", [])
    if authors:
        author_str = " and ".join(
            f"{a[1]}, {a[0]}" if len(a) > 1 and a[0] else a[1] if len(a) > 1 else a[0]
            for a in authors
        )
        lines.append(f"  author = {{{author_str}}},")

    if paper.get("date"):
        lines.append(f"  year = {{{paper['date'][:4]}}},")

    pub = paper.get("publicationTitle", "")
    if pub:
        if entry_type == "article":
            lines.append(f"  journal = {{{latex_escape(pub)}}},")
        elif entry_type == "inproceedings":
            lines.append(f"  booktitle = {{{latex_escape(pub)}}},")
        else:
            lines.append(f"  note = {{{latex_escape(pub)}}},")

    for field, bib_field in [
        ("volume", "volume"), ("issue", "number"), ("pages", "pages"),
        ("doi", "doi"), ("url", "url"), ("abstractNote", "abstract"),
        ("publisher", "publisher"), ("series", "series"),
        ("issn", "issn"), ("isbn", "isbn"),
    ]:
        val = paper.get(field)
        if val:
            lines.append(f"  {bib_field} = {{{val}}},")

    # Extra note: include arxiv ID, conference info, etc.
    extra_parts = []
    if paper.get("extra"):
        extra_parts.append(paper["extra"])
    if paper.get("conferenceName"):
        extra_parts.append(paper["conferenceName"])
    if extra_parts:
        lines.append(f"  note = {{{'; '.join(extra_parts)}}},")

    # Keywords from collections
    colls = paper.get("collections", [])
    if colls:
        lines.append(f"  keywords = {{{'; '.join(colls)}}},")

    lines.append("}")
    return "\n".join(lines)


def export_bibtex(papers: list, output_path: str) -> str:
    """Write BibTeX file, returns the path."""
    entries = [paper_to_bibtex(p) for p in papers]
    content = "% Auto-generated by add_to_zotero.py\n"
    content += "% Import into Zotero: File -> Import (Ctrl+Shift+I)\n\n"
    content += "\n\n".join(entries) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


# ─── SQLite helpers ──────────────────────────────────────────────────────────

def is_zotero_running() -> bool:
    """Check if Zotero process is running."""
    try:
        result = subprocess.run(["pgrep", "-f", "zotero"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def generate_key(existing_keys: set) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        key = ''.join(random.choices(chars, k=8))
        if key not in existing_keys:
            return key


def load_existing_keys(conn: sqlite3.Connection) -> set:
    return set(r[0] for r in conn.execute("SELECT key FROM items").fetchall())


def load_existing_dois(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT idv.value, id.itemID
        FROM itemData id
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        WHERE id.fieldID = 59
    """).fetchall()
    return {r[0]: r[1] for r in rows if r[0]}


def get_or_create_value_id(conn: sqlite3.Connection, value: str) -> int | None:
    if value is None:
        return None
    row = conn.execute(
        "SELECT valueID FROM itemDataValues WHERE value = ?", (value,)
    ).fetchone()
    if row:
        return row[0]
    max_id = conn.execute("SELECT MAX(valueID) FROM itemDataValues").fetchone()[0] or 0
    new_id = max_id + 1
    conn.execute("INSERT INTO itemDataValues (valueID, value) VALUES (?, ?)", (new_id, value))
    return new_id


def get_or_create_creator_id(conn: sqlite3.Connection, first_name: str, last_name: str) -> int:
    row = conn.execute(
        "SELECT creatorID FROM creators WHERE firstName = ? AND lastName = ?",
        (first_name, last_name),
    ).fetchone()
    if row:
        return row[0]
    max_id = conn.execute("SELECT MAX(creatorID) FROM creators").fetchone()[0] or 0
    new_id = max_id + 1
    conn.execute(
        "INSERT INTO creators (creatorID, firstName, lastName, fieldMode) VALUES (?, ?, ?, 0)",
        (new_id, first_name, last_name),
    )
    return new_id


def get_item_type_id(conn: sqlite3.Connection, type_name: str) -> int:
    row = conn.execute(
        "SELECT itemTypeID FROM itemTypes WHERE typeName = ?", (type_name,)
    ).fetchone()
    if row:
        return row[0]
    raise ValueError(f"Unknown itemType: {type_name}")


def get_collection_id(conn: sqlite3.Connection, collection_name: str) -> int | None:
    row = conn.execute(
        "SELECT collectionID FROM collections WHERE collectionName = ?", (collection_name,)
    ).fetchone()
    return row[0] if row else None


def insert_paper_direct(conn: sqlite3.Connection, paper: dict, existing_keys: set, existing_dois: dict) -> int | None:
    """Insert a single paper via SQLite. Returns itemID or None if duplicate."""
    doi = paper.get("doi", "").strip()
    if doi and doi in existing_dois:
        print(f"  [SKIP] DOI already exists: {doi}")
        return None

    title = paper.get("title", "").strip()
    if title:
        row = conn.execute("""
            SELECT id.itemID FROM itemData id
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.fieldID = 1 AND idv.value = ?
        """, (title,)).fetchone()
        if row:
            print(f"  [SKIP] Title already exists: {title[:60]}...")
            return None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    key = generate_key(existing_keys)
    existing_keys.add(key)

    item_type = paper.get("itemType", "journalArticle")
    item_type_id = get_item_type_id(conn, item_type)

    max_item = conn.execute("SELECT MAX(itemID) FROM items").fetchone()[0] or 0
    item_id = max_item + 1
    conn.execute("""
        INSERT INTO items (itemID, itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced)
        VALUES (?, ?, ?, ?, ?, 1, ?, 0, 0)
    """, (item_id, item_type_id, now, now, now, key))

    field_map = {}
    for row in conn.execute("SELECT fieldID, fieldName FROM fields").fetchall():
        field_map[row[1]] = row[0]

    field_values = {
        "title": paper.get("title"),
        "date": paper.get("date"),
        "url": paper.get("url"),
        "DOI": paper.get("doi"),
        "abstractNote": paper.get("abstractNote"),
        "publicationTitle": paper.get("publicationTitle"),
        "extra": paper.get("extra"),
        "volume": paper.get("volume"),
        "issue": paper.get("issue"),
        "pages": paper.get("pages"),
        "conferenceName": paper.get("conferenceName"),
        "libraryCatalog": paper.get("libraryCatalog", "arXiv.org"),
        "accessDate": paper.get("accessDate", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    }

    for field_name, value in field_values.items():
        if not value:
            continue
        fid = field_map.get(field_name)
        if not fid:
            continue
        vid = get_or_create_value_id(conn, value)
        conn.execute(
            "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)",
            (item_id, fid, vid),
        )

    authors = paper.get("authors", [])
    for i, author in enumerate(authors):
        first_name = author[0] if len(author) > 0 else ""
        last_name = author[1] if len(author) > 1 else ""
        creator_id = get_or_create_creator_id(conn, first_name, last_name)
        conn.execute(
            "INSERT INTO itemCreators (itemID, creatorID, creatorTypeID, orderIndex) VALUES (?, ?, 8, ?)",
            (item_id, creator_id, i),
        )

    collections = paper.get("collections", [])
    for coll_name in collections:
        coll_id = get_collection_id(conn, coll_name)
        if coll_id:
            conn.execute(
                "INSERT INTO collectionItems (collectionID, itemID) VALUES (?, ?)",
                (coll_id, item_id),
            )
        else:
            print(f"  [WARN] Collection '{coll_name}' not found")

    url = paper.get("url", "")
    if "arxiv.org/abs/" in url:
        arxiv_id = url.split("arxiv.org/abs/")[-1].split("?")[0].strip()
        if arxiv_id.endswith(".pdf"):
            arxiv_id = arxiv_id[:-4]
        attach_key = generate_key(existing_keys)
        existing_keys.add(attach_key)
        max_item_now = conn.execute("SELECT MAX(itemID) FROM items").fetchone()[0] or 0
        attach_item_id = max_item_now + 1
        attach_type_id = get_item_type_id(conn, "attachment")
        conn.execute("""
            INSERT INTO items (itemID, itemTypeID, dateAdded, dateModified, clientDateModified, libraryID, key, version, synced)
            VALUES (?, ?, ?, ?, ?, 1, ?, 0, 0)
        """, (attach_item_id, attach_type_id, now, now, now, attach_key))
        conn.execute("""
            INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path, syncState)
            VALUES (?, ?, 2, 'application/pdf', ?, 0)
        """, (attach_item_id, item_id, f"https://arxiv.org/pdf/{arxiv_id}"))

    print(f"  [OK] {title[:70]}...")
    return item_id


def run_direct_mode(papers: list, db_path: str) -> int:
    """Direct SQLite insertion. Returns number of papers inserted."""
    if not is_zotero_running():
        print("[WARN] Zotero is NOT running. Direct insertions may be lost on restart.")
        print("[WARN] Consider using --mode bibtex instead.")
        print()

    backup_path = db_path + f".bak_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    print(f"[INFO] Backing up to: {backup_path}")
    shutil.copy2(db_path, backup_path)

    tmp_db = "/tmp/zotero_modified.sqlite"
    shutil.copy2(db_path, tmp_db)
    conn = sqlite3.connect(tmp_db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    existing_keys = load_existing_keys(conn)
    existing_dois = load_existing_dois(conn)

    try:
        inserted = 0
        for paper in papers:
            result = insert_paper_direct(conn, paper, existing_keys, existing_dois)
            if result:
                inserted += 1
        conn.commit()

        if inserted > 0:
            shutil.copy2(tmp_db, db_path)
            print(f"\n[INFO] Inserted {inserted}/{len(papers)} papers into live database")
            print("[INFO] Check Zotero — the new items should appear within a few seconds.")
            if not is_zotero_running():
                print("[WARN] Zotero was closed during insert. Items may be lost on next startup.")
        else:
            print(f"\n[INFO] No new papers to insert (all {len(papers)} already exist)")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        print(f"[INFO] Original database unchanged. Backup at: {backup_path}")
        return 0
    finally:
        conn.close()
        if os.path.exists(tmp_db):
            os.remove(tmp_db)

    return inserted


def run_bibtex_mode(papers: list, output_dir: str) -> str:
    """Generate BibTeX file. Returns the file path."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"zotero_import_{timestamp}.bib")
    export_bibtex(papers, output_path)
    print(f"[INFO] BibTeX file written: {output_path}")
    print("[INFO] Import into Zotero: File -> Import (Ctrl+Shift+I)")
    print("[INFO] Select this file, then 'OK'. Existing papers will be skipped (dedup by DOI/title).")
    return output_path


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Add papers to Zotero — full-auto (direct) or semi-auto (bibtex)"
    )
    parser.add_argument("--papers", required=True, help="JSON file with papers metadata")
    parser.add_argument("--mode", choices=["auto", "direct", "bibtex"], default="auto",
                        help="auto: direct if Zotero running else bibtex | direct: force SQLite | bibtex: force BibTeX file (default: auto)")
    parser.add_argument("--db", default="/mnt/F/Obsidian/Zotero/zotero.sqlite", help="Zotero database path")
    parser.add_argument("--outdir", default="/mnt/F/Obsidian/Zotero", help="Output directory for BibTeX files")
    parser.add_argument("--dry-run", action="store_true", help="Validate JSON without inserting")
    args = parser.parse_args()

    with open(args.papers, "r", encoding="utf-8") as f:
        papers = json.load(f)

    if not papers:
        print("[ERROR] No papers in JSON file")
        sys.exit(1)

    if args.dry_run:
        print(f"[DRY RUN] Would process {len(papers)} papers")
        for p in papers:
            print(f"  - {p.get('title', 'NO TITLE')[:80]}")
        return

    # Determine effective mode
    mode = args.mode
    zotero_running = is_zotero_running()

    if mode == "auto":
        if zotero_running:
            mode = "direct"
        else:
            mode = "bibtex"

    print(f"[INFO] Mode: {mode.upper()} (Zotero {'running' if zotero_running else 'not running'})")
    print(f"[INFO] Papers to process: {len(papers)}")
    print()

    if mode == "direct":
        run_direct_mode(papers, args.db)
    else:
        run_bibtex_mode(papers, args.outdir)


if __name__ == "__main__":
    main()
