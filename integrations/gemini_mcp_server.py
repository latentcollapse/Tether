"""Tether Gemini MCP Server - simplified 2-tool FastMCP adapter for Gemini.

Provides a minimal MCP interface for Gemini to check its inbox and post results.
Uses direct SQLite access for simplicity (no LC-B encoding).

Requires: pip install fastmcp

Usage:
    python integrations/gemini_mcp_server.py
    TETHER_DB=/path/to/tether.db python integrations/gemini_mcp_server.py

Author: Jonas Cords (cordsjon) + Claude (Opus 4.6)
"""

import sqlite3
import os
import json
from datetime import datetime
from fastmcp import FastMCP

mcp = FastMCP("Tether-Gemini")
DB_PATH = os.environ.get("TETHER_DB", "tether.db")

def get_db_conn():
    """Connects to SQLite with WAL mode enabled for better concurrency."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

@mcp.tool()
def tether_inbox(recipient: str = "gemini") -> str:
    """
    Checks the postoffice for pending tasks assigned to a specific recipient.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE (recipient = ? OR recipient = 'all') "
        "AND status = 'pending' ORDER BY timestamp ASC",
        (recipient,)
    )
    rows = cursor.fetchall()
    if not rows:
        return "Inbox is empty."
    results = [dict(row) for row in rows]
    return json.dumps(results, indent=2)

@mcp.tool()
def tether_post_result(task_id: int, result_payload: str):
    """
    Posts the results of a task back to the postoffice and marks it as completed.
    """
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE messages SET result = ?, status = 'completed', completed_at = ? WHERE id = ?",
            (result_payload, datetime.now().isoformat(), task_id)
        )
        conn.commit()
        return f"Successfully updated Task #{task_id}."
    except Exception as e:
        return f"Error updating task: {str(e)}"
    finally:
        conn.close()

if __name__ == "__main__":
    mcp.run()
