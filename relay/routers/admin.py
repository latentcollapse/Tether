"""Relay operator administration routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, status

from relay.auth import get_db
from relay.db import RelayDB
from relay.models import AdminTierRequest, AdminTierResponse
from relay.tier import parse_tier

router = APIRouter(prefix="/v1/admin", tags=["admin"])


async def require_admin_key(authorization: str | None = Header(default=None)) -> None:
    """Validate the relay operator admin key."""
    admin_key = os.environ.get("TETHER_ADMIN_KEY")
    if not admin_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="admin key is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token != admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


@router.post("/agents/{agent_id}/tier", response_model=AdminTierResponse)
async def set_agent_tier(
    agent_id: str,
    body: AdminTierRequest,
    _: None = Depends(require_admin_key),
    db: RelayDB = Depends(get_db),
) -> AdminTierResponse:
    """Set an agent's relay tier."""
    tier = parse_tier(body.tier)
    if db.get_agent(agent_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")
    db.set_agent_tier(agent_id, tier.value)
    return AdminTierResponse(agent_id=agent_id, tier=tier.value)
