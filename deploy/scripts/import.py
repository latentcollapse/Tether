#!/usr/bin/env python3
"""
Tether handle importer — restores a pruned handle from archive.md into the DB
as a minimal stub record. Useful for audit trail lookups or re-linking a ticket.

The restored record has status='archived', lc_bytes=b'', and no message body —
it is a provenance marker only, not a resolvable message.

Usage:
    python scripts/import.py <handle>
    python scripts/import.py h&l_messages_abc123
    python scripts/import.py --db /path/to/db <handle>
    python scripts/import.py --list                  # list all archived handles
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ARCHIVE_PATH = Path(__file__).parent / "archive.md"
DEFAULT_DB = Path(__file__).parent.parent / "postoffice.db"


def parse_args():
    p = argparse.ArgumentParser(description="Import a pruned Tether handle from archive")
    p.add_argument("handle", nargs="?", help="Handle to import")
    p.add_argument("--db", type=str, default=str(DEFAULT_DB),
                   help="Path to Tether SQLite database")
    p.add_argument("--list", action="store_true",
                   help="List all handles in archive.md")
    return p.parse_args()


def parse_archive(archive_path: Path):
    """Parse archive.md and return list of handle row dicts."""
    if not archive_path.exists():
        return []

    rows = []
    in_table = False
    for line in archive_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("| handle |"):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table and line.startswith("|"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 8:
                handle = parts[0].strip("`")
                rows.append({
                    "handle": handle,
                    "table_name": parts[1],
                    "sender": parts[2],
                    "owner": parts[3],
                    "subject": parts[4],
                    "created_at": parts[5],
                    "ticket_id": parts[6],
                    "status": parts[7],
                })
        elif in_table and not line.startswith("|"):
            in_table = False
    return rows


def main():
    args = parse_args()
    rows = parse_archive(ARCHIVE_PATH)

    if args.list:
        if not rows:
            print("Archive is empty or not found.")
            return
        print(f"{'Handle':<45} {'Created':<20} {'From':<12} {'Ticket'}")
        print("-" * 95)
        for r in rows:
            print(f"{r['handle']:<45} {r['created_at']:<20} {r['sender']:<12} {r['ticket_id']}")
        return

    if not args.handle:
        print("Error: provide a handle or use --list", file=sys.stderr)
        sys.exit(1)

    match = next((r for r in rows if r["handle"] == args.handle), None)
    if not match:
        print(f"Handle not found in archive: {args.handle}", file=sys.stderr)
        sys.exit(1)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    existing = conn.execute(
        "SELECT handle FROM tether_handles WHERE handle = ?", (args.handle,)
    ).fetchone()

    if existing:
        print(f"Handle already exists in DB: {args.handle}")
        conn.close()
        return

    conn.execute("""
        INSERT INTO tether_handles
            (handle, table_name, lc_bytes, created_at, owner, sender, status, ticket_id)
        VALUES (?, ?, ?, ?, ?, ?, 'archived', ?)
    """, (
        match["handle"],
        match["table_name"] or "messages",
        b"",
        match["created_at"],
        match["owner"],
        match["sender"],
        match["ticket_id"] or None,
    ))
    conn.commit()
    conn.close()

    print(f"Imported stub for {args.handle} (status=archived, no message body)")


if __name__ == "__main__":
    main()
