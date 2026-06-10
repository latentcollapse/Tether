"""Tether HTTP API - lightweight REST service exposing the Tether database.

Endpoints:
    GET  /                      -> API overview + links
    GET  /tables                -> list all tables
    GET  /tables/{name}         -> all entries in a table (JSON)
    GET  /tables/{name}/csv     -> all entries in a table (CSV)
    GET  /messages              -> all messages across all tables
    GET  /messages/{handle}     -> resolve a single handle
    GET  /inbox/{agent}         -> inbox for a specific agent
    GET  /threads               -> list all threads
    GET  /threads/{name}        -> messages in a thread
    GET  /health                -> health check + DB stats

Usage:
    python -m tether.http_server                          # default port 7890
    python -m tether.http_server --port 7891 --host 0.0.0.0
    TETHER_DB=/path/to/postoffice.db python -m tether.http_server

Author: Jonas Cords (cordsjon) + Claude (Opus 4.6)
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from tether import SQLiteRuntime
from tether.exceptions import TetherError, E_HANDLE_UNRESOLVED


_db_path = os.environ.get("TETHER_DB", "tether.db")
_runtime: SQLiteRuntime | None = None


def set_db_path(path: str):
    global _db_path, _runtime
    _db_path = path
    _runtime = None

def get_runtime() -> SQLiteRuntime:
    global _runtime
    if _runtime is None:
        _runtime = SQLiteRuntime(_db_path)
    return _runtime


def _json_response(handler, data, status=200):
    body = json.dumps(data, indent=2, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _csv_response(handler, rows, filename="export.csv"):
    if not rows:
        _json_response(handler, {"error": "no data", "rows": 0}, 404)
        return
    output = io.StringIO()
    all_keys = []
    for row in rows:
        for k in row:
            if k not in all_keys:
                all_keys.append(k)
    writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat = {}
        for k, v in row.items():
            flat[k] = json.dumps(v, default=str) if isinstance(v, (dict, list)) else v
        writer.writerow(flat)
    body = output.getvalue().encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _snapshot_to_rows(table, snapshot):
    rows = []
    for handle, value in snapshot.items():
        row = {"handle": handle, "table": table}
        if isinstance(value, dict):
            row.update(value)
        else:
            row["value"] = value
        rows.append(row)
    return rows


class TetherHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {args[0]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        rt = get_runtime()

        try:
            if path == "" or path == "/":
                tables = rt.tables()
                total = sum(len(rt.handles(t)) for t in tables)
                _json_response(self, {
                    "service": "tether-http",
                    "db": _db_path,
                    "tables": tables,
                    "total_handles": total,
                    "endpoints": {
                        "/tables": "List all tables",
                        "/tables/{name}": "All entries in a table (JSON)",
                        "/tables/{name}/csv": "All entries in a table (CSV)",
                        "/messages": "All messages across all tables",
                        "/messages/{handle}": "Resolve a single handle",
                        "/inbox/{agent}": "Inbox for a specific agent",
                        "/threads": "List all threads",
                        "/threads/{name}": "Messages in a thread",
                        "/health": "Health check + DB stats",
                    }
                })

            elif path == "/health":
                tables = rt.tables()
                stats = {t: len(rt.handles(t)) for t in tables}
                _json_response(self, {
                    "status": "ok", "db": _db_path,
                    "db_exists": Path(_db_path).exists(),
                    "db_size_bytes": Path(_db_path).stat().st_size if Path(_db_path).exists() else 0,
                    "tables": stats, "total_handles": sum(stats.values()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

            elif path == "/tables":
                tables = rt.tables()
                _json_response(self, {"tables": {t: len(rt.handles(t)) for t in tables}})

            elif path.startswith("/tables/") and path.endswith("/csv"):
                table_name = path[len("/tables/"):-len("/csv")]
                rows = _snapshot_to_rows(table_name, rt.snapshot(table_name))
                _csv_response(self, rows, filename=f"{table_name}.csv")

            elif path.startswith("/tables/"):
                table_name = path[len("/tables/"):]
                rows = _snapshot_to_rows(table_name, rt.snapshot(table_name))
                rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
                _json_response(self, {"table": table_name, "count": len(rows), "entries": rows})

            elif path.startswith("/messages/&h_"):
                handle = path[len("/messages/"):]
                _json_response(self, {"handle": handle, "value": rt.resolve(handle)})

            elif path == "/messages":
                all_rows = []
                for t in rt.tables():
                    all_rows.extend(_snapshot_to_rows(t, rt.snapshot(t)))
                all_rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
                _json_response(self, {"count": len(all_rows), "messages": all_rows})

            elif path.startswith("/inbox/"):
                agent = path[len("/inbox/"):]
                snapshot = rt.snapshot("messages")
                inbox = [
                    {"handle": h, "from": m.get("from"), "to": m.get("to"),
                     "subject": m.get("subject"), "text": m.get("text"),
                     "timestamp": m.get("timestamp")}
                    for h, m in snapshot.items()
                    if isinstance(m, dict) and m.get("to") == agent
                ]
                inbox.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
                _json_response(self, {"for_agent": agent, "count": len(inbox), "messages": inbox})

            elif path == "/threads":
                snapshot = rt.snapshot("threads")
                threads = [
                    {"handle": h, "name": d.get("name"), "description": d.get("description")}
                    for h, d in snapshot.items() if isinstance(d, dict)
                ]
                _json_response(self, {"count": len(threads), "threads": threads})

            elif path.startswith("/threads/"):
                thread_name = path[len("/threads/"):]
                rows = _snapshot_to_rows(thread_name, rt.snapshot(thread_name))
                rows.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
                _json_response(self, {"thread": thread_name, "count": len(rows), "messages": rows})

            elif path == "/board/tickets":
                params = parse_qs(parsed.query)
                tickets = rt.board_query(
                    category=params.get("category", [None])[0],
                    tier=params.get("tier", [None])[0],
                    status=params.get("status", [None])[0],
                    owner=params.get("owner", [None])[0],
                    batch=params.get("batch", [None])[0],
                    sort=params.get("sort", ["newest"])[0]
                )
                _json_response(self, {"tickets": tickets})
                
            elif path == "/board/changelog":
                params = parse_qs(parsed.query)
                changelog = rt.board_changelog_query(
                    query_str=params.get("query", [None])[0]
                )
                _json_response(self, {"changelog": changelog})

            else:
                _json_response(self, {"error": "not found", "path": path}, 404)

        except E_HANDLE_UNRESOLVED as e:
            _json_response(self, {"error": "handle_not_found", "message": str(e)}, 404)
        except TetherError as e:
            _json_response(self, {"error": type(e).__name__, "message": str(e)}, 400)
        except Exception as e:
            _json_response(self, {"error": "internal", "message": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        rt = get_runtime()

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(body)
        except Exception as e:
            _json_response(self, {"error": "bad_request", "message": str(e)}, 400)
            return

        try:
            if path == "/send":
                required = {"from_agent", "to", "subject", "text"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                message_data = {
                    "from": data["from_agent"],
                    "to": data["to"],
                    "subject": data["subject"],
                    "text": data["text"],
                }
                handle = rt.collapse(
                    "messages",
                    message_data,
                    owner=data["to"],
                    sender=data["from_agent"],
                    tags=data.get("tags"),
                )
                _json_response(self, {
                    "handle": handle,
                    "status": "sent",
                    "from": data["from_agent"],
                    "to": data["to"],
                    "subject": data["subject"],
                })

            elif path == "/thread/reply":
                required = {"thread", "from_agent", "text"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                message_data = {
                    "from": data["from_agent"],
                    "text": data["text"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                handle = rt.collapse(
                    data["thread"],
                    message_data,
                    sender=data["from_agent"],
                )
                _json_response(self, {"handle": handle, "status": "sent", "thread": data["thread"]})

            elif path == "/board/propose":
                required = {"category", "tier", "title", "description", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                handle = rt.board_propose(
                    category=data["category"],
                    tier=data["tier"],
                    title=data["title"],
                    description=data["description"],
                    actor=data["from_agent"]
                )
                _json_response(self, {"handle": handle, "status": "proposed"})

            elif path == "/board/accept":
                required = {"id", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                actor = data["from_agent"]
                if actor not in ["claude", "matt"]:
                    _json_response(self, {"error": "unauthorized", "message": "Only admins can accept proposed tickets"}, 403)
                    return
                real_id = rt.board_accept(
                    proposed_id=data["id"],
                    actor=actor,
                    tier=data.get("tier")
                )
                _json_response(self, {"id": real_id, "status": "accepted"})

            elif path == "/board/author":
                required = {"category", "tier", "title", "description", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                actor = data["from_agent"]
                if actor not in ["claude", "matt"]:
                    _json_response(self, {"error": "unauthorized", "message": "Only admins can author tickets directly"}, 403)
                    return
                status = data.get("status", "open")
                real_id = rt.board_author(
                    category=data["category"],
                    tier=data["tier"],
                    title=data["title"],
                    description=data["description"],
                    actor=actor,
                    batch=data.get("batch"),
                    principle=data.get("principle"),
                    bible_ref=data.get("bible_ref"),
                    gate=data.get("gate"),
                    blocks=data.get("blocks"),
                    blocked_by=data.get("blocked_by"),
                    status=status
                )
                _json_response(self, {"id": real_id, "status": status})

            elif path == "/board/dormant":
                required = {"id", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                actor = data["from_agent"]
                if actor not in ["claude", "matt"]:
                    _json_response(self, {"error": "unauthorized", "message": "Only admins can mark tickets as dormant"}, 403)
                    return
                rt.board_dormant(
                    ticket_id=data["id"],
                    actor=actor
                )
                _json_response(self, {"id": data["id"], "status": "dormant"})

            elif path == "/board/revive":
                required = {"id", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                actor = data["from_agent"]
                if actor not in ["claude", "matt"]:
                    _json_response(self, {"error": "unauthorized", "message": "Only admins can revive tickets"}, 403)
                    return
                rt.board_revive(
                    ticket_id=data["id"],
                    actor=actor
                )
                _json_response(self, {"id": data["id"], "status": "open"})

            elif path == "/board/claim":
                required = {"id", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                rt.board_claim(
                    ticket_id=data["id"],
                    actor=data["from_agent"]
                )
                _json_response(self, {"id": data["id"], "status": "claimed", "owner": data["from_agent"]})

            elif path == "/board/flag":
                required = {"id", "from_agent", "work_done"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                rt.board_flag(
                    ticket_id=data["id"],
                    actor=data["from_agent"],
                    work_done=data["work_done"]
                )
                _json_response(self, {"id": data["id"], "status": "ready", "work_done": data["work_done"]})

            elif path == "/board/finalize":
                required = {"id", "from_agent"}
                missing = required - set(data.keys())
                if missing:
                    _json_response(self, {"error": "missing_fields", "fields": list(missing)}, 400)
                    return
                actor = data["from_agent"]
                if actor not in ["claude", "matt"]:
                    _json_response(self, {"error": "unauthorized", "message": "Only admins can finalize tickets"}, 403)
                    return
                changelog_handle = rt.board_finalize(
                    ticket_id=data["id"],
                    actor=actor
                )
                _json_response(self, {"id": data["id"], "status": "done", "changelog_handle": changelog_handle})

            else:
                _json_response(self, {"error": "not found", "path": path}, 404)

        except Exception as e:
            _json_response(self, {"error": "internal", "message": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="Tether HTTP API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7890)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    if args.db:
        set_db_path(args.db)
    get_runtime()
    server = HTTPServer((args.host, args.port), TetherHTTPHandler)
    print(f"Tether HTTP API running on http://{args.host}:{args.port}")
    server.serve_forever()

if __name__ == "__main__":
    main()
