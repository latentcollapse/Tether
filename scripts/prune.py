#!/usr/bin/env python3
"""
Tether handle pruner — archives and deletes stale/expired messages older than
a configurable threshold. Appends pruned handles to scripts/archive.md before
deletion so the provenance trail is never lost.

Usage:
    python scripts/prune.py                        # default 24h threshold
    python scripts/prune.py --hours 48             # custom threshold
    python scripts/prune.py --dry-run              # preview without deleting
    python scripts/prune.py --db /path/to/db       # custom DB path
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ARCHIVE_PATH = Path(__file__).parent / "archive.md"
DEFAULT_DB = Path(__file__).parent.parent / "postoffice.db"


def parse_args():
    p = argparse.ArgumentParser(description="Prune stale Tether handles")
    p.add_argument("--hours", type=float, default=24.0,
                   help="Age threshold in hours (default: 24)")
    p.add_argument("--db", type=str, default=str(DEFAULT_DB),
                   help="Path to Tether SQLite database")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be pruned without modifying anything")
    return p.parse_args()


def fetch_prunable(conn, cutoff: datetime):
    """Return rows eligible for pruning: stale/expired and older than cutoff."""
    cursor = conn.execute("""
        SELECT handle, table_name, created_at, expires_at, owner,
               tags, sender, status, ticket_id
        FROM tether_handles
        WHERE status IN ('stale', 'expired')
          AND created_at < ?
        ORDER BY created_at ASC
    """, (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))
    return cursor.fetchall()


def append_to_archive(rows, archive_path: Path, threshold_hours: float):
    """Append pruned handles to archive.md as a markdown table."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_needed = not archive_path.exists() or archive_path.stat().st_size == 0

    with open(archive_path, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("# Tether Handle Archive\n\n")
            f.write("Append-only log of pruned handles. "
                    "Use `scripts/import.py` to restore a handle to the DB.\n\n")

        f.write(f"\n## Pruned {now} (threshold: {threshold_hours}h)\n\n")
        f.write("| handle | table | from | to | subject | created_at | ticket_id | status |\n")
        f.write("|--------|-------|------|----|---------|------------|-----------|--------|\n")

        for row in rows:
            handle = row["handle"]
            table = row["table_name"]
            sender = row["sender"] or ""
            owner = row["owner"] or ""
            created = row["created_at"] or ""
            ticket = row["ticket_id"] or ""
            status = row["status"] or ""

            # Extract subject from tags if present
            tags = row["tags"] or ""
            subject = ""
            if tags:
                import json as _json
                try:
                    tag_list = _json.loads(tags)
                    subject = ", ".join(tag_list)
                except Exception:
                    subject = tags

            f.write(f"| `{handle}` | {table} | {sender} | {owner} | "
                    f"{subject} | {created} | {ticket} | {status} |\n")


def prune(conn, handles):
    """Delete pruned handles and their read records."""
    handle_list = [row["handle"] for row in handles]
    placeholders = ",".join("?" * len(handle_list))
    conn.execute(f"DELETE FROM tether_reads WHERE handle IN ({placeholders})", handle_list)
    conn.execute(f"DELETE FROM tether_handles WHERE handle IN ({placeholders})", handle_list)
    conn.commit()


def main():
    args = parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = fetch_prunable(conn, cutoff)

    if not rows:
        print(f"Nothing to prune (threshold: {args.hours}h, cutoff: {cutoff:%Y-%m-%d %H:%M UTC})")
        conn.close()
        return

    print(f"Found {len(rows)} handle(s) eligible for pruning "
          f"(threshold: {args.hours}h, cutoff: {cutoff:%Y-%m-%d %H:%M UTC})")

    for row in rows:
        flag = "[dry-run] " if args.dry_run else ""
        print(f"  {flag}{row['handle']}  status={row['status']}  created={row['created_at']}")

    if args.dry_run:
        print("Dry run — no changes made.")
        conn.close()
        return

    append_to_archive(rows, ARCHIVE_PATH, args.hours)
    prune(conn, rows)
    conn.close()

    print(f"Pruned {len(rows)} handle(s). Archive updated: {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
