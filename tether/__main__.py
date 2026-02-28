#!/usr/bin/env python3
"""Tether CLI - command-line interface for Tether runtime."""

import argparse
import json
import sys
from tether import TetherRuntime, create_transport
from tether.exceptions import TetherError


def main():
    parser = argparse.ArgumentParser(
        description="Tether CLI - LLM-to-LLM messaging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tether collapse messages < data.json     Collapse JSON to handle
  tether resolve &h_messages_abc123       Resolve handle to JSON
  tether send messages < data.json         Collapse and queue for send
  tether receive &h_messages_abc123       Receive and resolve
  tether inbox                             List pending messages
  tether tables                            List all tables
  tether snapshot messages                 Show all messages in table
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # collapse command
    collapse_parser = subparsers.add_parser("collapse", help="Collapse JSON to handle")
    collapse_parser.add_argument("table", help="Table name")
    collapse_parser.add_argument("file", nargs="?", default="-", help="Input file (default: stdin)")
    
    # send command (collapse + queue)
    send_parser = subparsers.add_parser("send", help="Collapse and queue for transfer")
    send_parser.add_argument("table", help="Table/destination name")
    send_parser.add_argument("file", nargs="?", default="-", help="Input file (default: stdin)")
    
    # receive command
    receive_parser = subparsers.add_parser("receive", help="Receive and resolve a handle")
    receive_parser.add_argument("handle", help="Handle to receive")
    
    # resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve handle to value")
    resolve_parser.add_argument("handle", help="Handle to resolve")
    resolve_parser.add_argument("--pretty", "-p", action="store_true", help="Pretty print JSON")
    
    # inbox command
    inbox_parser = subparsers.add_parser("inbox", help="List pending messages in queue")
    
    # tables command
    tables_parser = subparsers.add_parser("tables", help="List all tables")
    
    # snapshot command
    snapshot_parser = subparsers.add_parser("snapshot", help="Show all values in a table")
    snapshot_parser.add_argument("table", help="Table name")
    
    # export/import
    export_parser = subparsers.add_parser("export", help="Export table")
    export_parser.add_argument("table", help="Table name")
    export_parser.add_argument("file", nargs="?", default="-", help="Output file")
    
    import_parser = subparsers.add_parser("import", help="Import table")
    import_parser.add_argument("table", help="Table name")
    import_parser.add_argument("file", nargs="?", default="-", help="Input file")

    # Transport options
    parser.add_argument("--db", default="tether.db", help="Database path")
    parser.add_argument("--transport", default="sqlite", choices=["sqlite", "memory"], 
                        help="Transport backend")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create runtime
    try:
        rt = TetherRuntime(db_path=args.db, transport=create_transport(args.transport))
    except Exception as e:
        print(f"Error: Failed to initialize: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.command == "collapse":
            data = _read_input(args.file)
            value = json.loads(data)
            handle = rt.collapse(args.table, value)
            print(handle)
        
        elif args.command == "send":
            data = _read_input(args.file)
            value = json.loads(data)
            handle = rt.send(args.table, value)
            print(f"Queued: {handle}")
            print(f"Send this handle to recipient: {handle}")
        
        elif args.command == "receive":
            value = rt.receive(args.handle)
            print(json.dumps(value, indent=2))
        
        elif args.command == "resolve":
            value = rt.resolve(args.handle)
            if args.pretty:
                print(json.dumps(value, indent=2))
            else:
                print(json.dumps(value))
        
        elif args.command == "inbox":
            pending = rt.inbox()
            if pending:
                print("Pending messages:")
                for h in pending:
                    print(f"  {h}")
            else:
                print("No pending messages")
        
        elif args.command == "tables":
            tables = rt.tables()
            if tables:
                print("Tables:")
                for t in tables:
                    print(f"  {t}")
            else:
                print("No tables")
        
        elif args.command == "snapshot":
            snapshot = rt.snapshot(args.table)
            if snapshot:
                print(f"Table '{args.table}':")
                for handle, value in snapshot.items():
                    print(f"  {handle}:")
                    print(f"    {json.dumps(value)[:100]}...")
            else:
                print(f"Table '{args.table}' is empty")
        
        elif args.command == "export":
            data = rt.export_table(args.table)
            hex_data = {k: v.hex() for k, v in data.items()}
            output = json.dumps({"table": args.table, "handles": hex_data})
            if args.file == "-":
                print(output)
            else:
                with open(args.file, "w") as f:
                    f.write(output)
                print(f"Exported {len(data)} handles to {args.file}")
        
        elif args.command == "import":
            if args.file == "-":
                data = json.load(sys.stdin)
            else:
                with open(args.file) as f:
                    data = json.load(f)
            hex_data = {k: bytes.fromhex(v) for k, v in data.get("handles", {}).items()}
            rt.import_table(args.table, hex_data)
            print(f"Imported {len(hex_data)} handles to table '{args.table}'")
    
    except TetherError as e:
        print(f"TetherError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        rt.close()


def _read_input(path: str) -> str:
    """Read from file or stdin."""
    if path == "-":
        return sys.stdin.read()
    with open(path) as f:
        return f.read()


if __name__ == "__main__":
    main()
