"""Handle routing routes."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from relay.auth import AgentContext, get_current_agent, get_db
from relay.db import RelayDB
from relay.models import BlobResponse, BlobUploadRequest, BlobUploadResponse, HandleStatusResponse, RouteHandleRequest, RouteHandleResponse
from relay.routers.ws import deliver_or_queue, handle_payload, manager
from relay.tier import parse_tier, record_message_or_response

router = APIRouter(prefix="/v1/handles", tags=["handles"])


@router.post("/route", response_model=RouteHandleResponse)
async def route_handle(
    body: RouteHandleRequest,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> RouteHandleResponse | JSONResponse:
    """Route a handle to another registered agent."""
    target = db.get_agent(body.to)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target agent not found")
    sender_tier = parse_tier(db.get_agent_tier(current.agent_id) or "free")
    limit_body = record_message_or_response(current.agent_id, sender_tier)
    if limit_body is not None:
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=limit_body)

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


@router.post("/blobs", response_model=BlobUploadResponse)
async def upload_blob(
    body: BlobUploadRequest,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> BlobUploadResponse:
    """Store relay-blind ciphertext bytes for cross-machine encrypted handles."""
    try:
        payload = base64.b64decode(body.payload_b64.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid payload_b64") from exc
    try:
        stored = db.store_blind_blob(body.handle, body.content_type, payload, current.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BlobUploadResponse(handle=body.handle, stored=stored)


@router.get("/blobs/{handle}", response_model=BlobResponse)
async def get_blob(
    handle: str,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> BlobResponse:
    """Fetch a relay-stored ciphertext blob when the caller participated in its route."""
    blob = db.get_blind_blob(handle)
    if blob is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="blob not found")
    if not db.agent_can_access_blob(current.agent_id, handle):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot access blob")
    return BlobResponse(
        handle=handle,
        content_type=str(blob["content_type"]),
        payload_b64=base64.b64encode(bytes(blob["payload"])).decode("ascii"),
    )


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
