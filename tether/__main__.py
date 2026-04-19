#!/usr/bin/env python3
"""Tether CLI - ergonomic command-line interface for Tether."""

import argparse
import json
import os
import socket
import sqlite3
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from tether.sqlite_runtime import SQLiteRuntime, _decode_resilient
from tether.exceptions import TetherError

DEFAULT_DASHBOARD_PORT = 3000


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _user_data_db_path() -> str:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "tether", "postoffice.db")
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return os.path.join(xdg_data_home, "tether", "postoffice.db")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "tether", "postoffice.db")


def _default_db_path() -> str:
    cwd_db = Path.cwd() / "postoffice.db"
    if cwd_db.exists():
        return str(cwd_db)

    repo_db = _repo_root() / "postoffice.db"
    if repo_db.exists():
        return str(repo_db)

    return _user_data_db_path()


def _ensure_db_parent(db_path: str) -> None:
    if not db_path or db_path == ":memory:":
        return
    parent = Path(db_path).expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Tether CLI - LLM-to-LLM messaging & organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=os.environ.get("TETHER_DB", _default_db_path()), help="Database path")
    
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

    return parser


def _dashboard_dist_dir() -> Path | None:
    env_path = os.environ.get("TETHER_DASHBOARD_DIST")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    repo_root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            repo_root / "tether-dashboard" / "dist",
            Path.cwd() / "tether-dashboard" / "dist",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None

def _dashboard_db_path() -> str:
    return os.environ.get("TETHER_DB") or _default_db_path()


def _find_free_port(start_port: int = DEFAULT_DASHBOARD_PORT) -> int:
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                port += 1
                continue
            return port
    raise RuntimeError("No free localhost port found")


def _connect_dashboard_db() -> sqlite3.Connection:
    db_path = _dashboard_db_path()
    _ensure_db_parent(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _decode_row_value(row: sqlite3.Row):
    try:
        return _decode_resilient(row["lc_bytes"])
    except Exception:
        return None


def _parse_tags(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(tag) for tag in value if str(tag).strip()]
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]


def _message_agents(row: sqlite3.Row, body) -> tuple[str, str]:
    payload = body if isinstance(body, dict) else {}
    from_agent = (
        payload.get("from")
        or payload.get("from_agent")
        or row["sender"]
        or row["owner"]
        or "unknown"
    )
    to_agent = payload.get("to") or payload.get("to_agent") or "unknown"
    return str(from_agent), str(to_agent)


def _message_status(row: sqlite3.Row, read_at=None) -> str:
    if read_at:
        return "read"
    status = str(row["status"] or "open").lower()
    if status in {"read", "closed"}:
        return status
    return "open"


def _message_summary(row: sqlite3.Row, read_at=None) -> dict:
    body = _decode_row_value(row)
    payload = body if isinstance(body, dict) else {}
    from_agent, to_agent = _message_agents(row, payload)
    return {
        "id": row["handle"],
        "handle": row["handle"],
        "from": from_agent,
        "to": to_agent,
        "subject": str(payload.get("subject") or "(no subject)"),
        "text": str(payload.get("text") or payload.get("content") or ""),
        "status": _message_status(row, read_at),
        "createdAt": payload.get("timestamp") or row["created_at"],
        "ticketId": row["ticket_id"],
    }


def _handle_result(row: sqlite3.Row) -> dict:
    body = _decode_row_value(row)
    table = row["table_name"]
    tags = _parse_tags(row["tags"])
    if table == "messages":
        payload = body if isinstance(body, dict) else {}
        from_agent, to_agent = _message_agents(row, payload)
        return {
            "kind": "message",
            "handle": row["handle"],
            "table": table,
            "fromAgent": from_agent,
            "toAgent": to_agent,
            "createdAt": payload.get("timestamp") or row["created_at"],
            "status": str(row["status"] or "open"),
            "ticketId": row["ticket_id"],
            "tags": tags,
            "subject": payload.get("subject") or "(no subject)",
            "text": payload.get("text") or payload.get("content") or "",
        }
    if row["handle"].startswith("h&l_tree_") and isinstance(body, list):
        return {"kind": "tree", "handle": row["handle"], "handles": body}
    if row["handle"].startswith("h&l_blob_") and isinstance(body, dict):
        return {
            "kind": "blob",
            "handle": row["handle"],
            "contentType": body.get("content_type") or body.get("contentType") or "application/octet-stream",
            "bytesB64": body.get("bytes_b64") or body.get("bytesB64") or "",
            "sizeBytes": body.get("size_bytes") or body.get("sizeBytes") or 0,
        }
    return {
        "kind": "inline",
        "handle": row["handle"],
        "value": {
            "table": table,
            "createdAt": row["created_at"],
            "status": row["status"],
            "ticketId": row["ticket_id"],
            "tags": tags,
            "content": body,
        },
    }


def _handle_summary(row: sqlite3.Row) -> dict:
    detail = _handle_result(row)
    base = {
        "handle": row["handle"],
        "table": row["table_name"],
        "kind": detail["kind"],
        "createdAt": detail.get("createdAt") or row["created_at"],
        "status": row["status"] or "open",
        "ticketId": row["ticket_id"],
        "tags": _parse_tags(row["tags"]),
    }
    if detail["kind"] == "message":
        base["fromAgent"] = detail["fromAgent"]
        base["toAgent"] = detail["toAgent"]
        base["subject"] = detail.get("text", "")[:80] if not detail.get("subject") else detail.get("subject")
    return base


def _create_dashboard_app(dist_dir: Path):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse

    app = FastAPI(title="Tether Dashboard")

    @app.get("/health")
    def health():
        return {"ok": True, "mode": "lite", "db": _dashboard_db_path()}

    @app.get("/api/messages")
    def messages(agent: str = "", limit: int = 50):
        limit = max(1, min(limit, 500))
        rows_limit = limit if not agent else max(limit * 4, 200)
        with _connect_dashboard_db() as conn:
            rows = conn.execute(
                """
                SELECT h.handle, h.table_name, h.lc_bytes, h.created_at, h.owner,
                       h.tags, h.sender, h.status, h.ticket_id, r.read_at
                FROM tether_handles h
                LEFT JOIN tether_reads r ON h.handle = r.handle AND r.agent = ?
                WHERE h.table_name = 'messages'
                ORDER BY h.created_at DESC
                LIMIT ?
                """,
                (agent or "", rows_limit),
            ).fetchall()

        result = []
        for row in rows:
            item = _message_summary(row, row["read_at"] if agent else None)
            if agent and item["to"] != agent:
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return result

    @app.post("/api/messages")
    async def send_message(payload: dict):
        to_agent = str(payload.get("to") or "").strip()
        subject = str(payload.get("subject") or "").strip()
        text = str(payload.get("text") or "").strip()
        if not to_agent or not subject or not text:
            raise HTTPException(status_code=400, detail="to, subject, and text are required")
        value = {
            "from": str(payload.get("from") or "dashboard"),
            "to": to_agent,
            "subject": subject,
            "text": text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        ticket_id = str(payload.get("ticketId") or "").strip() or None
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            handle = runtime.collapse(
                "messages",
                value,
                owner=value["from"],
                tags=["dashboard"],
                ticket_id=ticket_id,
            )
        finally:
            runtime.close()
        return {"handle": handle}

    _GHOST_AGENTS = {"unknown", "test_bridge", "dashboard"}

    @app.get("/api/agents")
    def agents(days: int = 2):
        from datetime import timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
        with _connect_dashboard_db() as conn:
            rows = conn.execute(
                """
                SELECT handle, table_name, lc_bytes, created_at, owner, tags,
                       sender, status, ticket_id
                FROM tether_handles
                WHERE table_name = 'messages'
                ORDER BY created_at ASC
                """
            ).fetchall()

        today = datetime.now(timezone.utc).date()
        agents_by_id: dict[str, dict] = {}
        edges: dict[tuple[str, str], dict] = {}

        def ensure_agent(agent_id: str, created_at: str) -> dict:
            name = agent_id.split("@", 1)[0]
            existing = agents_by_id.get(agent_id)
            if existing:
                existing["lastSeen"] = max(existing["lastSeen"], created_at)
                existing["registrationDate"] = min(existing["registrationDate"], created_at)
                return existing
            agent_type = "Human" if name.lower() in {"matt", "human", "user"} else "AI Agent"
            agents_by_id[agent_id] = {
                "id": agent_id,
                "name": name,
                "type": agent_type,
                "description": "Observed in postoffice.db",
                "isAdmin": name.lower() == "matt",
                "status": "online",
                "lastSeen": created_at,
                "registrationDate": created_at,
                "messagesSentToday": 0,
                "messagesReceivedToday": 0,
                "totalMessages": 0,
                "apiKeyLastDigits": "",
                "isLocal": True,
            }
            return agents_by_id[agent_id]

        for row in rows:
            body = _decode_row_value(row)
            from_agent, to_agent = _message_agents(row, body)
            if from_agent in _GHOST_AGENTS or to_agent in _GHOST_AGENTS:
                continue
            created_at = str(row["created_at"])
            try:
                row_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
            except Exception:
                row_date = None

            sender = ensure_agent(from_agent, created_at)
            recipient = ensure_agent(to_agent, created_at)
            sender["totalMessages"] += 1
            recipient["totalMessages"] += 1
            if row_date == today:
                sender["messagesSentToday"] += 1
                recipient["messagesReceivedToday"] += 1

            key = (from_agent, to_agent)
            edge = edges.setdefault(
                key,
                {
                    "id": f"e-{from_agent}-{to_agent}",
                    "source": from_agent,
                    "target": to_agent,
                    "count": 0,
                    "todayCount": 0,
                    "lastSeen": created_at,
                },
            )
            edge["count"] += 1
            edge["lastSeen"] = max(edge["lastSeen"], created_at)
            if row_date == today:
                edge["todayCount"] += 1

        active_agents = {
            aid: a for aid, a in agents_by_id.items()
            if a["lastSeen"] >= cutoff
        }
        active_edges = [
            e for e in edges.values()
            if e["source"] in active_agents and e["target"] in active_agents
        ]

        return {
            "agents": sorted(active_agents.values(), key=lambda item: item["id"]),
            "edges": sorted(active_edges, key=lambda item: item["count"], reverse=True),
        }

    @app.get("/api/handles")
    def handles(limit: int = 100, offset: int = 0):
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        with _connect_dashboard_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM tether_handles").fetchone()[0]
            rows = conn.execute(
                """
                SELECT handle, table_name, lc_bytes, created_at, owner, tags,
                       sender, status, ticket_id
                FROM tether_handles
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return {
            "items": [_handle_summary(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/handles/{handle}")
    def handle_detail(handle: str):
        with _connect_dashboard_db() as conn:
            row = conn.execute(
                """
                SELECT handle, table_name, lc_bytes, created_at, owner, tags,
                       sender, status, ticket_id
                FROM tether_handles
                WHERE handle = ?
                """,
                (handle,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Handle not found")
        return _handle_result(row)

    @app.get("/api/stats")
    def stats():
        agent_response = agents()
        with _connect_dashboard_db() as conn:
            total_handles = conn.execute("SELECT COUNT(*) FROM tether_handles").fetchone()[0]
            total_messages = conn.execute(
                "SELECT COUNT(*) FROM tether_handles WHERE table_name = 'messages'"
            ).fetchone()[0]
        return {
            "messages": total_messages,
            "agents": len(agent_response["agents"]),
            "handles": total_handles,
        }

    @app.get("/api/feed")
    def feed(limit: int = 50):
        limit = max(1, min(limit, 500))
        with _connect_dashboard_db() as conn:
            rows = conn.execute(
                """
                SELECT handle, table_name, lc_bytes, created_at, owner, tags,
                       sender, status, ticket_id
                FROM tether_handles
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        items = []
        for row in rows:
            body = _decode_row_value(row)
            if row["table_name"] == "messages":
                from_agent, to_agent = _message_agents(row, body)
            else:
                from_agent = row["sender"] or row["owner"] or "tether"
                to_agent = row["table_name"]
            payload = body if isinstance(body, dict) else {}
            items.append(
                {
                    "id": row["handle"],
                    "timestamp": payload.get("timestamp") or row["created_at"],
                    "from": from_agent,
                    "to": to_agent,
                    "handle": row["handle"],
                    "ticketId": row["ticket_id"],
                    "table": row["table_name"],
                }
            )
        return items

    @app.get("/{path:path}", include_in_schema=False)
    def static_or_index(path: str):
        target = (dist_dir / path).resolve()
        dist_root = dist_dir.resolve()
        if path and target.is_file() and dist_root in target.parents:
            return FileResponse(target)
        return FileResponse(dist_dir / "index.html")

    return app


def _run_dashboard(parser: argparse.ArgumentParser) -> None:
    dist_dir = _dashboard_dist_dir()
    if dist_dir is None:
        print("Tether dashboard is not built yet.")
        print("Build it with: cd tether-dashboard && npm run build")
        print()
        parser.print_help()
        return

    port = _find_free_port()
    url = f"http://localhost:{port}"
    app = _create_dashboard_app(dist_dir)

    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass
    print(f"Tether dashboard running at {url} — Ctrl+C to stop", flush=True)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main():
    parser = _build_parser()
    if len(sys.argv) == 1:
        _run_dashboard(parser)
        return

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    db_path = args.db
    if not os.path.exists(db_path) and args.command != "collapse":
        workspace_db = os.environ.get("TETHER_DB", _default_db_path())
        if os.path.exists(workspace_db):
            db_path = workspace_db

    _ensure_db_parent(db_path)
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
