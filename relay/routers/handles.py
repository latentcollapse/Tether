"""Handle routing routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from relay.auth import AgentContext, get_current_agent, get_db
from relay.db import RelayDB
from relay.models import HandleStatusResponse, RouteHandleRequest, RouteHandleResponse
from relay.routers.ws import deliver_or_queue, handle_payload, manager

router = APIRouter(prefix="/v1/handles", tags=["handles"])


@router.post("/route", response_model=RouteHandleResponse)
async def route_handle(
    body: RouteHandleRequest,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> RouteHandleResponse:
    """Route a handle to another registered agent."""
    target = db.get_agent(body.to)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target agent not found")

    row_id = db.queue_handle(
        handle=body.handle,
        from_agent=current.agent_id,
        to_agent=body.to,
        subject=body.subject,
        ticket_id=body.ticket_id,
        tags=body.tags,
        status="queued",
    )
    row = {
        "id": row_id,
        "handle": body.handle,
        "from_agent": current.agent_id,
        "subject": body.subject,
        "ticket_id": body.ticket_id,
        "tags": body.tags,
        "queued_at": None,
    }
    delivered = await deliver_or_queue(db, row_id, body.to, handle_payload(row))
    return RouteHandleResponse(queued=not delivered, delivered=delivered)


@router.get("/{handle}/status", response_model=HandleStatusResponse)
async def handle_status(
    handle: str,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> HandleStatusResponse:
    """Return the latest known routing status for a handle."""
    _ = current
    found = db.handle_status(handle)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="handle not found")
    return HandleStatusResponse(handle=handle, status=found)
