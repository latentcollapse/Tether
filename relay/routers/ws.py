"""Relay websocket routing."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from relay import auth
from relay.db import RelayDB, utc_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["websocket"])


class ConnectionManager:
    """Tracks active agent websocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    def is_connected(self, agent_id: str) -> bool:
        """Return whether an agent has an active websocket."""
        return agent_id in self._connections

    async def connect(self, agent_id: str, websocket: WebSocket) -> None:
        """Accept and track an agent websocket."""
        await websocket.accept()
        self._connections[agent_id] = websocket

    def disconnect(self, agent_id: str) -> None:
        """Remove an agent websocket."""
        self._connections.pop(agent_id, None)

    async def send_handle(self, agent_id: str, payload: dict[str, Any]) -> bool:
        """Push a handle payload to an online agent."""
        websocket = self._connections.get(agent_id)
        if websocket is None:
            return False
        await websocket.send_json(payload)
        return True


manager = ConnectionManager()


def handle_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Build the websocket handle push payload."""
    return {
        "type": "handle",
        "handle": row["handle"],
        "from": row["from_agent"],
        "subject": row["subject"],
        "ticket_id": row.get("ticket_id"),
        "tags": row.get("tags", []),
        "timestamp": row.get("queued_at") or utc_now(),
    }


async def deliver_or_queue(db: RelayDB, row_id: int, to_agent: str, payload: dict[str, Any]) -> bool:
    """Deliver a handle immediately when the recipient websocket is online."""
    delivered = await manager.send_handle(to_agent, payload)
    if delivered:
        db.mark_delivered(row_id)
    return delivered


async def flush_pending(db: RelayDB, agent_id: str) -> None:
    """Flush queued handles to a newly connected agent."""
    for row in db.pending_for_agent(agent_id):
        delivered = await manager.send_handle(agent_id, handle_payload(row))
        if delivered:
            db.mark_delivered(int(row["id"]))


@router.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str) -> None:
    """Persistent websocket for push delivery."""
    db = auth.current_db()
    try:
        context = auth.authenticate_websocket(db, websocket)
    except HTTPException as exc:
        logger.warning("websocket authentication failed", extra={"agent_id": agent_id, "error": str(exc)})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if context.agent_id != agent_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(agent_id, websocket)
    db.set_online(agent_id, True)
    try:
        await flush_pending(db, agent_id)
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("websocket disconnected", extra={"agent_id": agent_id})
    finally:
        manager.disconnect(agent_id)
        db.set_online(agent_id, False)
