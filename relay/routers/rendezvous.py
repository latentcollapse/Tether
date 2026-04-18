"""Relay rendezvous endpoints for WAN PAKE setup."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from relay.auth import AgentContext, get_current_agent, get_db
from relay.db import RelayDB
from relay.models import (
    RendezvousPeerResponse,
    RendezvousSessionCreateResponse,
    RendezvousSessionRequest,
    RendezvousWaitingResponse,
)
from relay.tier import Tier, feature_upgrade_response, parse_tier, tier_config

router = APIRouter(prefix="/v1/rendezvous", tags=["rendezvous"])

_TTL_SECONDS = 30.0
_sessions_lock = threading.RLock()


@dataclass
class _RendezvousSession:
    token: str
    initiator_agent_id: str
    initiator_addr: str
    peer_addr: str | None
    expires_at: float


_sessions: dict[str, _RendezvousSession] = {}


@router.post("/session", response_model=RendezvousSessionCreateResponse)
async def create_session(
    body: RendezvousSessionRequest,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> RendezvousSessionCreateResponse | JSONResponse:
    """Create a temporary rendezvous session for WAN PAKE setup."""
    _prune_expired_sessions()
    current_tier = parse_tier(db.get_agent_tier(current.agent_id) or Tier.FREE.value)
    if not tier_config(current_tier).features.pake_wan:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=feature_upgrade_response(current_tier, "pake_wan"),
        )

    token = str(uuid.uuid4())
    session = _RendezvousSession(
        token=token,
        initiator_agent_id=current.agent_id,
        initiator_addr=body.addr,
        peer_addr=None,
        expires_at=time.monotonic() + _TTL_SECONDS,
    )
    with _sessions_lock:
        _sessions[token] = session
    return RendezvousSessionCreateResponse(token=token, expires_in=int(_TTL_SECONDS))


@router.post("/session/{token}", response_model=RendezvousPeerResponse)
async def join_session(
    token: str,
    body: RendezvousSessionRequest,
) -> RendezvousPeerResponse:
    """Join a rendezvous session and retrieve the initiator address."""
    session = _get_session(token)
    with _sessions_lock:
        session.peer_addr = body.addr
    return RendezvousPeerResponse(peer_addr=session.initiator_addr)


@router.get("/session/{token}", response_model=RendezvousPeerResponse | RendezvousWaitingResponse)
async def poll_session(
    token: str,
) -> RendezvousPeerResponse | JSONResponse:
    """Poll a rendezvous session for the peer address."""
    session = _get_session(token)
    if session.peer_addr is None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=RendezvousWaitingResponse(status="waiting").model_dump(),
        )
    return RendezvousPeerResponse(peer_addr=session.peer_addr)


def _prune_expired_sessions() -> None:
    """Drop expired rendezvous sessions."""
    now = time.monotonic()
    with _sessions_lock:
        expired = [token for token, session in _sessions.items() if session.expires_at <= now]
        for token in expired:
            _sessions.pop(token, None)


def _get_session(token: str) -> _RendezvousSession:
    """Get a non-expired rendezvous session or raise 404."""
    _prune_expired_sessions()
    with _sessions_lock:
        session = _sessions.get(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rendezvous session not found")
    return session
