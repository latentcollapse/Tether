#!/usr/bin/env python3
"""Tether CLI - ergonomic command-line interface for Tether."""

import argparse
import json
import sys
import os
from datetime import datetime
from tether.sqlite_runtime import SQLiteRuntime, _decode_resilient
from tether.exceptions import TetherError

def main():
    parser = argparse.ArgumentParser(
        description="Tether CLI - LLM-to-LLM messaging & organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=os.environ.get("TETHER_DB", "tether.db"), help="Database path")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # collapse command
    collapse_parser = subparsers.add_parser("collapse", help="Collapse JSON to handle")
    collapse_parser.add_argument("table", help="Table name")
    collapse_parser.add_argument("file", nargs="?", default="-", help="Input file (default: stdin)")
    collapse_parser.add_argument("--owner", help="Set handle owner")
    collapse_parser.add_argument("--tags", help="Comma-separated tags")
    collapse_parser.add_argument("--ttl", type=int, help="TTL in seconds")
    
    # resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve handle to value")
    resolve_parser.add_argument("handle", help="Handle to resolve")
    resolve_parser.add_argument("--agent", help="Mark as read for this agent")
    resolve_parser.add_argument("--pretty", "-p", action="store_true", default=True, help="Pretty print JSON")
    resolve_parser.add_argument("--no-pretty", dest="pretty", action="store_false")
    
    # metadata command
    metadata_parser = subparsers.add_parser("metadata", help="Show handle metadata")
    metadata_parser.add_argument("handle", help="Handle to inspect")
    metadata_parser.add_argument("--agent", help="Check read status for this agent")
    
    # inbox command
    inbox_parser = subparsers.add_parser("inbox", help="List handles in a table (organized view)")
    inbox_parser.add_argument("table", nargs="?", default="messages", help="Table name")
    inbox_parser.add_argument("--agent", default="human", help="Agent name for read status (default: human)")
    inbox_parser.add_argument("--tag", help="Filter by tag")
    inbox_parser.add_argument("--limit", type=int, default=20, help="Max handles to show")
    
    # tables command
    subparsers.add_parser("tables", help="List all tables")
    
    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a handle")
    delete_parser.add_argument("handle", help="Handle to delete")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    db_path = args.db
    if not os.path.exists(db_path) and args.command != "collapse":
        workspace_db = "/mnt/d/kilo-workspace/Tether/tether.db"
        if os.path.exists(workspace_db):
            db_path = workspace_db

    rt = SQLiteRuntime(db_path=db_path)
    
    try:
        if args.command == "collapse":
            data_str = _read_input(args.file)
            value = json.loads(data_str)
            tags = args.tags.split(",") if args.tags else None
            handle = rt.collapse(args.table, value, ttl_seconds=args.ttl, owner=args.owner, tags=tags)
            print(handle)
        
        elif args.command == "resolve":
            value = rt.resolve(args.handle, for_agent=args.agent)
            if args.pretty:
                print(json.dumps(value, indent=2))
            else:
                print(json.dumps(value))
        
        elif args.command == "metadata":
            meta = rt.metadata(args.handle, for_agent=args.agent)
            print(json.dumps(meta, indent=2))
            
        elif args.command == "inbox":
            # Advanced view with read status
            query = """
                SELECT h.handle, h.created_at, h.owner, h.tags, h.lc_bytes, r.read_at
                FROM tether_handles h
                LEFT JOIN tether_reads r ON h.handle = r.handle AND r.agent = ?
                WHERE h.table_name = ?
            """
            params = [args.agent, args.table]
            if args.tag:
                query += " AND h.tags LIKE ?"
                params.append(f"%{args.tag}%")
            
            # Sort: Unread first, then by date desc
            query += " ORDER BY (r.read_at IS NULL) DESC, h.created_at DESC LIMIT ?"
            params.append(args.limit)
            
            cursor = rt._conn.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                print(f"No handles found in table '{args.table}'")
                return
                
            print(f"{'S':<2} | {'CREATED AT':<20} | {'OWNER':<10} | {'TAGS':<15} | {'HANDLE'}")
            print("-" * 85)
            for row in rows:
                status = "●" if row["read_at"] is None else "○" # Filled circle for unread, empty for read
                tags = row["tags"] if row["tags"] else ""
                owner = row["owner"] if row["owner"] else "-"
                print(f"{status:<2} | {row['created_at']:<20} | {owner:<10} | {tags:<15} | {row['handle']}")
                
                try:
                    content = _decode_resilient(row["lc_bytes"])
                    if isinstance(content, dict):
                        subject = content.get("subject", content.get("topic", ""))
                        if subject:
                            print(f"     Subject: {subject}")
                        msg_from = content.get("from", "")
                        if msg_from:
                            snippet = content.get("text", content.get("content", ""))[:60].replace("\n", " ")
                            print(f"     From: {msg_from} - {snippet}...")
                except:
                    pass
                print()

        elif args.command == "tables":
            for t in rt.tables():
                count = len(rt.handles(t))
                print(f"{t:<20} ({count} handles)")
        
        elif args.command == "delete":
            if rt.delete(args.handle):
                print(f"Deleted {args.handle}")
            else:
                print(f"Handle {args.handle} not found")
    
    except TetherError as e:
        print(f"TetherError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        rt.close()

def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path) as f:
        return f.read()

if __name__ == "__main__":
    main()
