"""API key lifecycle routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from relay.auth import AgentContext, generate_api_key, get_current_agent, get_db, hash_api_key
from relay.db import RelayDB
from relay.models import KeyCreateRequest, KeyCreateResponse, KeyInfo, KeyRotateResponse

router = APIRouter(prefix="/v1/keys", tags=["keys"])


def require_key_owner(key: dict[str, object] | None, current: AgentContext) -> dict[str, object]:
    """Return a key row if the authenticated agent owns it."""
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="key not found")
    if str(key["agent_id"]) != current.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage another agent's key")
    return key


@router.post("", response_model=KeyCreateResponse)
async def create_key(
    body: KeyCreateRequest,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> KeyCreateResponse:
    """Issue an additional managed API key for the authenticated agent."""
    if body.agent_id != current.agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot issue another agent's key")
    if db.get_agent(body.agent_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent not found")

    api_key = generate_api_key()
    key = db.create_key(body.agent_id, body.label, hash_api_key(api_key))
    return KeyCreateResponse(
        key_id=str(key["key_id"]),
        api_key=api_key,
        agent_id=str(key["agent_id"]),
        created_at=str(key["created_at"]),
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: str,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> Response:
    """Revoke a managed API key."""
    require_key_owner(db.get_key(key_id), current)
    db.revoke_key(key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{key_id}/rotate", response_model=KeyRotateResponse)
async def rotate_key(
    key_id: str,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> KeyRotateResponse:
    """Atomically revoke a managed key and issue its replacement."""
    key = require_key_owner(db.get_key(key_id), current)
    if key.get("revoked_at") is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key is already revoked")

    api_key = generate_api_key()
    replacement = db.rotate_key(key_id, hash_api_key(api_key))
    if replacement is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key is already revoked")
    return KeyRotateResponse(new_key_id=str(replacement["key_id"]), api_key=api_key)


@router.get("", response_model=list[KeyInfo])
async def list_keys(
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> list[KeyInfo]:
    """List managed API keys for the authenticated agent."""
    return [
        KeyInfo(
            key_id=str(row["key_id"]),
            agent_id=str(row["agent_id"]),
            label=row.get("label"),
            created_at=str(row["created_at"]),
            revoked_at=row.get("revoked_at"),
        )
        for row in db.list_keys_for_agent(current.agent_id)
    ]
