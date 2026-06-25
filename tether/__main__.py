#!/usr/bin/env python3
"""Tether CLI - ergonomic command-line interface for Tether."""

import argparse
import json
import os
import socket
import sqlite3
import sys
import urllib.request
import webbrowser
from datetime import datetime, timezone
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


def _send_message_with_ping(
    runtime: SQLiteRuntime,
    *,
    to_agent: str,
    subject: str,
    text: str,
    from_agent: str,
    tags: list[str] | None = None,
    ttl_seconds: int | None = None,
    ticket_id: str | None = None,
) -> str:
    value = {
        "from": from_agent,
        "to": to_agent,
        "subject": subject,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    handle = runtime.collapse(
        "messages",
        value,
        ttl_seconds=ttl_seconds,
        owner=to_agent,
        tags=tags,
        sender=from_agent,
        ticket_id=ticket_id,
    )
    ping_url = runtime.get_ping_url(to_agent)
    if ping_url:
        payload = json.dumps({
            "event": "tether_message",
            "to": to_agent,
            "from": from_agent,
            "subject": subject,
            "handle": handle,
        }).encode("utf-8")
        req = urllib.request.Request(
            ping_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2):
                pass
        except Exception:
            # HTTP blocked (sandboxed process) — fall back to notify file
            # which PROMPT_COMMAND picks up on the recipient's next render.
            try:
                notify_path = os.path.join(os.path.expanduser("~"), ".tether_notify")
                with open(notify_path, "w", encoding="utf-8") as f:
                    f.write(f"[Tether] From agent: {from_agent}  Handle: '{handle}'\n")
            except Exception:
                pass
    return handle


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

    # send command
    send_parser = subparsers.add_parser("send", help="Send a message and trigger recipient autoping")
    send_parser.add_argument("to", help="Recipient agent name")
    send_parser.add_argument("subject", help="Message subject")
    send_parser.add_argument("text", help="Message body")
    send_parser.add_argument("--from-agent", default="unknown", help="Sender agent name")
    send_parser.add_argument("--tags", help="Comma-separated tags")
    send_parser.add_argument("--ttl", type=int, help="TTL in seconds")
    send_parser.add_argument("--ticket-id", help="Optional ticket ID")
    
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

    # serve command — agent-as-service wake receiver
    serve_parser = subparsers.add_parser(
        "serve", help="Run this agent's wake receiver (no-tmux delivery)")
    serve_parser.add_argument("--agent", required=True, help="This agent's identity")
    serve_parser.add_argument("--port", type=int, default=0, help="0 = auto-assign")
    serve_parser.add_argument("--wake", default=None, help="Shell command to run per tmail")
    serve_parser.add_argument("--inject", action="store_true", help="Also use tmux/desktop fallback")
    serve_parser.add_argument("--delivery-mode", choices=("desktop", "tmux"), default="desktop")

    # mux command — run an agent inside a Tether-owned PTY (no-tmux delivery)
    mux_parser = subparsers.add_parser(
        "mux", help="Run an agent inside a Tether PTY; tmails autofire into its input")
    mux_parser.add_argument("--agent", required=True, help="Agent identity")
    mux_parser.add_argument("--port", type=int, default=0, help="0 = auto-assign")
    mux_parser.add_argument("--quiet-ms", type=int, default=800,
                            help="Stream must be quiet this long before injecting")
    mux_parser.add_argument("mux_command", nargs=argparse.REMAINDER,
                            help="-- followed by the agent command")

    # agents command — view/edit the registry (source of truth)
    agents_parser = subparsers.add_parser("agents", help="View or edit the agent registry")
    agents_parser.add_argument("--add", metavar="ID", help="Add/update an agent id")
    agents_parser.add_argument("--name", help="Display name (with --add)")
    agents_parser.add_argument("--cli", help="CLI label (with --add)")
    # dest must not be 'command' — that's the subparsers dest and would collide
    agents_parser.add_argument("--command", dest="launch_command", help="Launch command (with --add)")
    agents_parser.add_argument("--remove", metavar="ID", help="Remove an agent id")

    # konsole command — inspect/drive Konsole tabs over D-Bus (KDE auto-wire)
    konsole_parser = subparsers.add_parser("konsole", help="List or inject into Konsole tabs (KDE)")
    konsole_parser.add_argument("konsole_action", choices=("list", "send"), help="list tabs or send text")
    konsole_parser.add_argument("--session", help="Session path, e.g. /Sessions/7 (with send)")
    konsole_parser.add_argument("--service", help="Konsole D-Bus service (defaults to first found)")
    konsole_parser.add_argument("--text", help="Text to inject (with send)")
    konsole_parser.add_argument("--no-enter", action="store_true", help="Don't press Enter after text")

    return parser


def _dashboard_dist_dir() -> Path | None:
    env_path = os.environ.get("TETHER_DASHBOARD_DIST")
    candidates = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    repo_root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            repo_root / "tether-dashboard" / "dist" / "app" / "browser",
            repo_root / "tether-dashboard" / "dist" / "app",
            repo_root / "tether-dashboard" / "dist",
            Path.cwd() / "tether-dashboard" / "dist" / "app" / "browser",
            Path.cwd() / "tether-dashboard" / "dist" / "app",
            Path.cwd() / "tether-dashboard" / "dist",
        ]
    )

    for candidate in candidates:
        # Angular 19 SSR: root shell is index.csr.html; pre-rendered routes have index.html
        if (candidate / "index.csr.html").is_file() or (candidate / "index.html").is_file():
            return candidate
    return None

def _dashboard_db_path() -> str:
    return os.environ.get("TETHER_DB") or _default_db_path()


_DASHBOARD_PORT = DEFAULT_DASHBOARD_PORT


def _dashboard_server_port() -> int:
    return _DASHBOARD_PORT


def _resolve_handle_text_main(handle: str) -> str:
    """Resolve a tmail handle to its instruction text (best-effort)."""
    if not handle:
        return ""
    try:
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            value = rt.resolve(handle)
        finally:
            rt.close()
        if isinstance(value, dict):
            return str(value.get("text") or value.get("content") or "")
        return str(value) if value is not None else ""
    except Exception:
        return ""


def _detect_running_clis() -> list[dict]:
    """Scan /proc for processes matching registry launch commands.

    Returns [{agent, pid, wrapped}] where `wrapped` means the process is a
    `tether mux` host (so injection works) vs. a bare CLI launched directly
    (detectable, but can't be woken until relaunched through the mux).
    Linux-only; returns [] elsewhere or on any error.
    """
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return []
    try:
        from tether.agent_config import load_agents
        registry = load_agents()
    except Exception:
        return []
    # Map command basename → agent id
    by_basename: dict[str, str] = {}
    for a in registry:
        cmd = (a.get("command") or "").strip()
        if cmd:
            by_basename[os.path.basename(cmd.split()[0])] = a["id"]

    hits: list[dict] = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().split(b"\x00")
        except (OSError, ValueError):
            continue
        argv = [p.decode("utf-8", "replace") for p in cmdline if p]
        if not argv:
            continue
        wrapped = any("tether" in a for a in argv) and "mux" in argv
        # A mux host: find which agent via --agent
        if wrapped and "--agent" in argv:
            try:
                agent_id = argv[argv.index("--agent") + 1]
                hits.append({"agent": agent_id, "pid": int(entry.name), "wrapped": True})
                continue
            except (ValueError, IndexError):
                pass
        # A bare CLI: match the executable basename to the registry
        base = os.path.basename(argv[0])
        if base in by_basename:
            hits.append({"agent": by_basename[base], "pid": int(entry.name), "wrapped": False})
    return hits


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
    import asyncio
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
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
        ticket_id = str(payload.get("ticketId") or "").strip() or None
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            handle = _send_message_with_ping(
                runtime,
                to_agent=to_agent,
                subject=subject,
                text=text,
                from_agent=str(payload.get("from") or "dashboard"),
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

    @app.get("/api/board/tickets")
    def get_board_tickets(
        category: str = None,
        tier: str = None,
        status: str = None,
        owner: str = None,
        batch: str = None,
        sort: str = "newest",
    ):
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            tickets = runtime.board_query(
                category=category or None,
                tier=tier or None,
                status=status or None,
                owner=owner or None,
                batch=batch or None,
                sort=sort,
            )
            return {"tickets": tickets}
        finally:
            runtime.close()

    @app.get("/api/board/changelog")
    def get_board_changelog(query: str = None):
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            changelog = runtime.board_changelog_query(query_str=query or None)
            return {"changelog": changelog}
        finally:
            runtime.close()

    @app.get("/api/board/whiteboard")
    def get_board_whiteboard():
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            return {"content": runtime.get_whiteboard()}
        finally:
            runtime.close()

    @app.post("/api/board/whiteboard")
    def post_board_whiteboard(payload: dict):
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            content = payload.get("content", "")
            runtime.update_whiteboard(content)
            return {"success": True}
        finally:
            runtime.close()

    @app.post("/api/board/propose")
    def post_board_propose(payload: dict):
        required = {"category", "tier", "title", "description", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            handle = runtime.board_propose(
                category=payload["category"],
                tier=payload["tier"],
                title=payload["title"],
                description=payload["description"],
                actor=payload["from_agent"],
            )
            return {"handle": handle, "status": "proposed"}
        finally:
            runtime.close()

    @app.post("/api/board/accept")
    def post_board_accept(payload: dict):
        required = {"id", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        actor = payload["from_agent"]
        if actor not in ["claude", "matt"]:
            raise HTTPException(status_code=403, detail="Only admins can accept proposed tickets")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            real_id = runtime.board_accept(
                proposed_id=payload["id"],
                actor=actor,
                tier=payload.get("tier"),
            )
            return {"id": real_id, "status": "accepted"}
        finally:
            runtime.close()

    @app.post("/api/board/author")
    def post_board_author(payload: dict):
        required = {"category", "tier", "title", "description", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        actor = payload["from_agent"]
        if actor not in ["claude", "matt"]:
            raise HTTPException(status_code=403, detail="Only admins can author tickets directly")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            status = payload.get("status", "open")
            real_id = runtime.board_author(
                category=payload["category"],
                tier=payload["tier"],
                title=payload["title"],
                description=payload["description"],
                actor=actor,
                batch=payload.get("batch"),
                principle=payload.get("principle"),
                bible_ref=payload.get("bible_ref"),
                gate=payload.get("gate"),
                blocks=payload.get("blocks"),
                blocked_by=payload.get("blocked_by"),
                status=status
            )
            return {"id": real_id, "status": status}
        finally:
            runtime.close()

    @app.post("/api/board/dormant")
    def post_board_dormant(payload: dict):
        required = {"id", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        actor = payload["from_agent"]
        if actor not in ["claude", "matt"]:
            raise HTTPException(status_code=403, detail="Only admins can mark tickets as dormant")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.board_dormant(
                ticket_id=payload["id"],
                actor=actor
            )
            return {"id": payload["id"], "status": "dormant"}
        finally:
            runtime.close()

    @app.post("/api/board/revive")
    def post_board_revive(payload: dict):
        required = {"id", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        actor = payload["from_agent"]
        if actor not in ["claude", "matt"]:
            raise HTTPException(status_code=403, detail="Only admins can revive tickets")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.board_revive(
                ticket_id=payload["id"],
                actor=actor
            )
            return {"id": payload["id"], "status": "open"}
        finally:
            runtime.close()

    @app.post("/api/board/claim")
    def post_board_claim(payload: dict):
        required = {"id", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.board_claim(
                ticket_id=payload["id"],
                actor=payload["from_agent"],
            )
            return {"id": payload["id"], "status": "claimed", "owner": payload["from_agent"]}
        finally:
            runtime.close()

    @app.post("/api/board/flag")
    def post_board_flag(payload: dict):
        required = {"id", "from_agent", "work_done"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.board_flag(
                ticket_id=payload["id"],
                actor=payload["from_agent"],
                work_done=payload["work_done"],
            )
            return {"id": payload["id"], "status": "ready", "work_done": payload["work_done"]}
        finally:
            runtime.close()

    @app.post("/api/board/finalize")
    def post_board_finalize(payload: dict):
        required = {"id", "from_agent"}
        missing = required - set(payload.keys())
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing fields: {list(missing)}")
        actor = payload["from_agent"]
        if actor not in ["claude", "matt"]:
            raise HTTPException(status_code=403, detail="Only admins can finalize tickets")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            changelog_handle = runtime.board_finalize(
                ticket_id=payload["id"],
                actor=actor,
            )
            return {"id": payload["id"], "status": "done", "changelog_handle": changelog_handle}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            runtime.close()

    # --- Channel API ---

    @app.get("/api/channels")
    def get_channels():
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            return runtime.channel_list()
        finally:
            runtime.close()

    @app.post("/api/channels")
    def post_channel(payload: dict):
        if "name" not in payload:
            raise HTTPException(status_code=400, detail="Missing field: name")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            channel_id = runtime.channel_create(
                name=payload["name"],
                description=payload.get("description", ""),
                members=payload.get("members", []),
            )
            channels = runtime.channel_list()
            chan = next((c for c in channels if c["id"] == channel_id), {"id": channel_id})
            return chan
        finally:
            runtime.close()

    @app.post("/api/channels/delete")
    def delete_channel(payload: dict):
        if "id" not in payload:
            raise HTTPException(status_code=400, detail="Missing field: id")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime._conn.execute("DELETE FROM tether_channel_messages WHERE channel_id = ?", [payload["id"]])
            runtime._conn.execute("DELETE FROM tether_channel_members WHERE channel_id = ?", [payload["id"]])
            runtime._conn.execute("DELETE FROM tether_channels WHERE id = ?", [payload["id"]])
            runtime._conn.commit()
            return {"id": payload["id"], "status": "deleted"}
        finally:
            runtime.close()

    @app.post("/api/channels/join")
    def join_channel(payload: dict):
        if "id" not in payload or "agent" not in payload:
            raise HTTPException(status_code=400, detail="Missing field: id or agent")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.channel_join(payload["id"], payload["agent"])
            return {"id": payload["id"], "agent": payload["agent"], "status": "joined"}
        finally:
            runtime.close()

    @app.post("/api/channels/leave")
    def leave_channel(payload: dict):
        if "id" not in payload or "agent" not in payload:
            raise HTTPException(status_code=400, detail="Missing field: id or agent")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            runtime.channel_leave(payload["id"], payload["agent"])
            return {"id": payload["id"], "agent": payload["agent"], "status": "left"}
        finally:
            runtime.close()

    @app.get("/api/channels/{channel_id}/messages")
    def get_channel_messages(channel_id: str, limit: int = 100, offset: int = 0):
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            return runtime.channel_get_messages(channel_id, limit=limit, offset=offset)
        finally:
            runtime.close()

    @app.post("/api/channels/{channel_id}/messages")
    def send_channel_message(channel_id: str, payload: dict):
        if "sender" not in payload or "body" not in payload:
            raise HTTPException(status_code=400, detail="Missing field: sender or body")
        runtime = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            msg_id = runtime.channel_send_message(
                channel_id,
                sender=payload["sender"],
                body=payload["body"],
                thread_id=payload.get("threadId"),
            )
            return {"id": msg_id, "channelId": channel_id, "status": "sent"}
        finally:
            runtime.close()

    # ── Multiplexer: Presence ─────────────────────────────────────────────────

    @app.get("/api/presence")
    def get_presence():
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            return {"agents": rt.presence_list()}
        finally:
            rt.close()

    @app.post("/api/presence/heartbeat")
    def post_heartbeat(payload: dict):
        agent = str(payload.get("agent") or "").strip()
        if not agent:
            raise HTTPException(status_code=400, detail="agent required")
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            rt.presence_heartbeat(agent)
            return {"ok": True}
        finally:
            rt.close()

    @app.post("/api/presence/connect")
    def post_connect(payload: dict):
        """Spawn a ping_daemon for the given agent (LOCAL tier).

        Zero-config: the caller supplies only an agent name. The dashboard
        picks a free port, spawns the daemon in 'auto' mode (which discovers
        the agent's tmux pane and falls back to desktop notify), and shares
        its own database with the daemon via the TETHER_DB env var.
        """
        import subprocess as _sp
        import os as _os
        import socket as _sock
        agent = str(payload.get("agent") or "").strip()
        if not agent:
            raise HTTPException(status_code=400, detail="agent required")
        mode = str(payload.get("mode") or "auto").strip()
        if mode not in ("auto", "desktop", "tmux"):
            mode = "auto"
        # Auto-assign a free ephemeral port — the user never needs to know it
        with _sock.socket() as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
        db_path = _dashboard_db_path()
        rt = SQLiteRuntime(db_path=db_path)
        try:
            # Kill any stale daemon for this agent first
            existing = [a for a in rt.presence_list(stale_seconds=86400)
                        if a["agent"] == agent and a.get("pid")]
            for stale in existing:
                try:
                    _os.kill(stale["pid"], 15)  # SIGTERM
                except (ProcessLookupError, TypeError):
                    pass
            # CRITICAL: share the dashboard's DB with the daemon so heartbeats
            # land in the same file the dashboard reads.
            child_env = dict(_os.environ)
            child_env["TETHER_DB"] = db_path
            # Spawn the agent-as-service wake receiver. It owns an HTTP socket,
            # queues tmails for loop/one-shot agents to pull, and registers its
            # own endpoint. --inject keeps the tmux/desktop bridge alive so
            # terminal REPLs still wake until they migrate to listener mode.
            cmd = [sys.executable, "-m", "tether.agent_server",
                   "--agent", agent, "--port", str(port)]
            if mode in ("auto", "tmux", "desktop"):
                cmd.append("--inject")
                cmd.extend(["--delivery-mode", "tmux" if mode == "tmux" else "desktop"])
            proc = _sp.Popen(
                cmd,
                cwd=str(_repo_root()),
                env=child_env,
                start_new_session=True,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
            )
            # agent_server registers its own endpoint, but set it here too so the
            # URL is present immediately for callers that read before first beat.
            rt.set_ping_url(agent, f"http://localhost:{port}")
            rt.presence_register(agent, pid=proc.pid, ping_port=port)
            return {"ok": True, "agent": agent, "pid": proc.pid, "port": port, "mode": mode}
        finally:
            rt.close()

    @app.get("/api/registry")
    def get_registry():
        """The agent registry — source of truth for known team members."""
        from tether.agent_config import load_agents, config_path
        return {"agents": load_agents(), "path": config_path()}

    @app.post("/api/registry")
    def post_registry(payload: dict):
        from tether.agent_config import upsert_agent
        if not payload.get("id"):
            raise HTTPException(status_code=400, detail="id required")
        return {"agents": upsert_agent(payload)}

    @app.post("/api/registry/delete")
    def delete_registry(payload: dict):
        from tether.agent_config import remove_agent
        agent_id = str(payload.get("id") or "").strip()
        if not agent_id:
            raise HTTPException(status_code=400, detail="id required")
        return {"agents": remove_agent(agent_id)}

    @app.get("/api/konsole/sessions")
    def konsole_sessions():
        """Live Konsole tabs with a best-guess agent identity from the registry."""
        from tether import konsole_driver
        if not konsole_driver.available():
            return {"available": False, "sessions": []}
        from tether.agent_config import load_agents
        registry = load_agents()
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            bound = {b["session"]: b["agent"] for b in rt.konsole_bindings()}
        finally:
            rt.close()
        sessions = konsole_driver.list_sessions()
        for s in sessions:
            s["boundAgent"] = bound.get(s["session"])
            s["guessedAgent"] = s["boundAgent"] or konsole_driver.guess_agent(s, registry)
        return {"available": True, "sessions": sessions}

    @app.post("/api/konsole/bind")
    def konsole_bind(payload: dict):
        """Bind an agent id to a Konsole tab: stamp the title, register delivery."""
        from tether import konsole_driver
        agent = str(payload.get("agent") or "").strip()
        service = str(payload.get("service") or "").strip()
        session = str(payload.get("session") or "").strip()
        if not (agent and service and session):
            raise HTTPException(status_code=400, detail="agent, service, session required")
        konsole_driver.set_title(service, session, agent)
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            rt.konsole_bind(agent, service, session)
            # Delivery for a konsole agent routes back to this server, which
            # injects via D-Bus. That endpoint becomes the agent's ping URL.
            deliver_url = f"http://localhost:{_dashboard_server_port()}/api/konsole/deliver?agent={agent}"
            rt.set_ping_url(agent, deliver_url)
            rt.presence_register(agent)
            return {"ok": True, "agent": agent, "session": session}
        finally:
            rt.close()

    @app.post("/api/konsole/unbind")
    def konsole_unbind(payload: dict):
        agent = str(payload.get("agent") or "").strip()
        if not agent:
            raise HTTPException(status_code=400, detail="agent required")
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            rt.konsole_unbind(agent)
            rt.presence_offline(agent)
            return {"ok": True}
        finally:
            rt.close()

    @app.post("/api/konsole/deliver")
    def konsole_deliver(agent: str, payload: dict):
        """Ping target for konsole-bound agents: resolve handle, type into the tab."""
        from tether import konsole_driver
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            binding = rt.konsole_binding(agent)
        finally:
            rt.close()
        if not binding:
            raise HTTPException(status_code=404, detail=f"no konsole binding for {agent}")
        handle = str(payload.get("handle") or "")
        sender = str(payload.get("from") or "unknown")
        text = payload.get("text") or _resolve_handle_text_main(handle)
        text = " ".join(str(text).split())
        if text:
            line = f"[Tether from {sender}] {text} (handle: {handle})"
        else:
            line = f"[Tether from {sender}] new message — resolve {handle}"
        ok = konsole_driver.send_line(binding["service"], binding["session"], line)
        return {"ok": ok, "agent": agent, "injected": ok}

    @app.get("/api/discover")
    def discover_agents():
        """Discover agents available to register right now, without ports.

        Combines three sources so the dashboard dropdown always has real,
        actionable candidates:
          - tmux: live panes matching known agent patterns (codex, gemini, …)
          - history: recent message senders not yet present
          - presence: agents already registered in the presence table
        """
        from tether import ping_daemon as _pd
        candidates: dict[str, dict] = {}  # keyed by agent id, first (most live) wins

        # 1. Live tmux panes (only meaningful while tmux is still in the loop)
        try:
            for hit in _pd.discover_tmux_agents():
                candidates.setdefault(hit["agent"], {
                    "agent": hit["agent"], "source": "tmux", "detail": hit["pane"],
                })
        except Exception:
            pass

        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            # 2. Presence table — agents with a live (or recent) mux/daemon
            try:
                for p in rt.presence_list(stale_seconds=86400):
                    candidates.setdefault(p["agent"], {
                        "agent": p["agent"], "source": "presence", "detail": p["status"],
                    })
            except Exception:
                pass
            # 3. Running CLIs detected by process scan, matched to the registry
            try:
                for hit in _detect_running_clis():
                    candidates.setdefault(hit["agent"], {
                        "agent": hit["agent"], "source": "process",
                        "detail": f"running pid {hit['pid']} ({'wrapped' if hit['wrapped'] else 'unwrapped'})",
                    })
            except Exception:
                pass
            # 4. Recent message senders
            try:
                for a in agents().get("agents", []):
                    name = a.get("name")
                    if name:
                        candidates.setdefault(name, {
                            "agent": name, "source": "history", "detail": "seen in messages",
                        })
            except Exception:
                pass
            # 5. Registry — every known team member, even if not running yet
            try:
                from tether.agent_config import load_agents as _load_reg
                for a in _load_reg():
                    candidates.setdefault(a["id"], {
                        "agent": a["id"], "source": "registry",
                        "detail": a.get("cli", "registered"),
                    })
            except Exception:
                pass
        finally:
            rt.close()

        return {"agents": sorted(candidates.values(), key=lambda x: x["agent"])}

    @app.post("/api/presence/disconnect")
    def post_disconnect(payload: dict):
        agent = str(payload.get("agent") or "").strip()
        if not agent:
            raise HTTPException(status_code=400, detail="agent required")
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            agents = [a for a in rt.presence_list(stale_seconds=86400) if a["agent"] == agent]
            for a in agents:
                if a.get("pid"):
                    try:
                        import os as _os
                        _os.kill(a["pid"], 15)
                    except (ProcessLookupError, TypeError):
                        pass
            rt.presence_offline(agent)
            return {"ok": True}
        finally:
            rt.close()

    # ── Multiplexer: Routes ───────────────────────────────────────────────────

    @app.get("/api/routes")
    def get_routes():
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            return {"routes": rt.route_list()}
        finally:
            rt.close()

    @app.post("/api/routes")
    def post_route(payload: dict):
        from_agent = str(payload.get("from") or payload.get("from_agent") or "").strip()
        to_agent = str(payload.get("to") or payload.get("to_agent") or "").strip()
        if not from_agent or not to_agent:
            raise HTTPException(status_code=400, detail="from and to required")
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            route_id = rt.route_create(from_agent, to_agent)
            return {"ok": True, "id": route_id, "from": from_agent, "to": to_agent}
        finally:
            rt.close()

    @app.delete("/api/routes/{route_id}")
    def delete_route(route_id: str):
        rt = SQLiteRuntime(db_path=_dashboard_db_path())
        try:
            deleted = rt.route_delete(route_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="route not found")
            return {"ok": True}
        finally:
            rt.close()

    # ── WebSocket: Agent presence stream ──────────────────────────────────────

    @app.websocket("/ws/agents")
    async def ws_agents(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                rt = SQLiteRuntime(db_path=_dashboard_db_path())
                try:
                    agents = rt.presence_list()
                    routes = rt.route_list()
                finally:
                    rt.close()
                await websocket.send_json({"type": "presence", "agents": agents, "routes": routes})
                await asyncio.sleep(5)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    @app.websocket("/ws/feed")
    async def ws_feed(websocket: WebSocket):
        await websocket.accept()
        last_ts: str | None = None
        try:
            while True:
                with _connect_dashboard_db() as conn:
                    if last_ts is None:
                        # On first connect, return latest 50 items as seed
                        rows = conn.execute(
                            """SELECT handle, table_name, created_at, owner, sender, tags, ticket_id
                               FROM tether_handles ORDER BY created_at DESC LIMIT 50""",
                        ).fetchall()
                        rows = list(reversed(rows))
                    else:
                        rows = conn.execute(
                            """SELECT handle, table_name, created_at, owner, sender, tags, ticket_id
                               FROM tether_handles WHERE created_at > ?
                               ORDER BY created_at ASC LIMIT 50""",
                            (last_ts,),
                        ).fetchall()

                    if rows:
                        last_ts = rows[-1]["created_at"]
                        items = []
                        for row in rows:
                            body = _decode_row_value(row)
                            if row["table_name"] == "messages":
                                from_agent, to_agent = _message_agents(row, body)
                            else:
                                from_agent = row["sender"] or row["owner"] or "tether"
                                to_agent = row["table_name"]
                            items.append({
                                "id": row["handle"],
                                "handle": row["handle"],
                                "from": from_agent,
                                "to": to_agent,
                                "table": row["table_name"],
                                "timestamp": row["created_at"],
                            })
                        await websocket.send_json({"type": "feed", "items": items})
                    elif last_ts is None:
                        last_ts = datetime.now(timezone.utc).isoformat()

                await asyncio.sleep(0.75)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    @app.get("/{path:path}", include_in_schema=False)
    def static_or_index(path: str):
        target = (dist_dir / path).resolve()
        dist_root = dist_dir.resolve()
        if path and target.is_file() and dist_root in target.parents:
            return FileResponse(target)
        # Angular 19 SSR: try pre-rendered route index.html, then fall back to CSR shell
        if path:
            prerendered = (dist_dir / path / "index.html").resolve()
            if prerendered.is_file() and dist_root in prerendered.parents:
                return FileResponse(prerendered)
        csr_shell = dist_dir / "index.csr.html"
        if csr_shell.is_file():
            return FileResponse(csr_shell)
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
    global _DASHBOARD_PORT
    _DASHBOARD_PORT = port
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
    # Preprocess sys.argv to move --db to the front (before the subcommand) so that
    # argparse parses it successfully regardless of where it appears in the CLI call.
    new_argv = [sys.argv[0]]
    db_args = []
    other_args = []
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--db":
            if i + 1 < len(sys.argv):
                db_args = ["--db", sys.argv[i+1]]
                i += 2
                continue
        elif arg.startswith("--db="):
            db_args = [arg]
            i += 1
            continue
        other_args.append(arg)
        i += 1
        
    sys.argv = new_argv + db_args + other_args

    parser = _build_parser()
    if len(sys.argv) == 1:
        _run_dashboard(parser)
        return

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # serve runs its own long-lived HTTP receiver — hand off before touching the
    # shared runtime. It manages its own DB connection + heartbeat.
    if args.command == "serve":
        serve_argv = ["tether-serve", "--agent", args.agent, "--port", str(args.port)]
        if args.wake:
            serve_argv.extend(["--wake", args.wake])
        if args.inject:
            serve_argv.append("--inject")
        serve_argv.extend(["--delivery-mode", args.delivery_mode])
        sys.argv = serve_argv
        from tether import agent_server
        agent_server.main()
        return

    # mux also runs a long-lived process (PTY host) — hand off before runtime.
    if args.command == "mux":
        command = args.mux_command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            # No explicit command — resolve it from the agent registry so a bare
            # `tether mux --agent codex` just works.
            from tether.agent_config import get_command
            command = get_command(args.agent)
        if not command:
            print(f"No command for agent '{args.agent}'. Add it to the registry "
                  f"(tether agents) or pass one: tether mux --agent {args.agent} -- <cli>")
            return
        from tether.pty_mux import PtyMux
        mux = PtyMux(args.agent, command, args.quiet_ms)
        sys.exit(mux.run(args.port))

    # agents registry management (no shared runtime needed)
    if args.command == "agents":
        from tether import agent_config
        if args.remove:
            agent_config.remove_agent(args.remove)
            print(f"Removed '{args.remove}'.")
        elif args.add:
            agent_config.upsert_agent({
                "id": args.add,
                "name": args.name or args.add,
                "cli": args.cli or "",
                "command": args.launch_command or "",
            })
            print(f"Saved '{args.add}'.")
        print(f"Registry: {agent_config.config_path()}")
        for a in agent_config.load_agents():
            print(f"  {a['id']:<10} {a.get('name',''):<10} {a.get('command','(no command)')}")
        return

    # konsole inspection / injection (KDE D-Bus)
    if args.command == "konsole":
        from tether import konsole_driver
        from tether.agent_config import load_agents
        if not konsole_driver.available():
            print("Konsole D-Bus not available (qdbus not found).")
            return
        if args.konsole_action == "list":
            reg = load_agents()
            for s in konsole_driver.list_sessions():
                guess = konsole_driver.guess_agent(s, reg) or "-"
                flag = " [tmux-nested]" if s["ambiguous"] else ""
                print(f"  {s['service']}  {s['session']:<14} {s['proc']:<16} guess={guess}{flag}")
                print(f"      cmd: {s['cmdline'][:100]}")
            return
        if args.konsole_action == "send":
            if not (args.session and args.text):
                print("send requires --session and --text")
                return
            service = args.service or (konsole_driver.konsole_services() or [None])[0]
            if not service:
                print("No Konsole service found.")
                return
            ok = konsole_driver.send_line(service, args.session, args.text, submit=not args.no_enter)
            print("injected." if ok else "injection failed.")
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

        elif args.command == "send":
            tags = args.tags.split(",") if args.tags else None
            handle = _send_message_with_ping(
                rt,
                to_agent=args.to,
                subject=args.subject,
                text=args.text,
                from_agent=args.from_agent,
                tags=tags,
                ttl_seconds=args.ttl,
                ticket_id=args.ticket_id,
            )
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
