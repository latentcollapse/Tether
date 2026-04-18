"""Authentication helpers for the Tether relay."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

import bcrypt
from fastapi import Depends, Header, HTTPException, WebSocket, status

from .config import get_config
from .db import RelayDB

_db: RelayDB | None = None


@dataclass(frozen=True)
class AgentContext:
    """Authenticated relay agent."""

    agent_id: str
    name: str


def generate_api_key() -> str:
    """Generate a relay API key."""
    return f"{get_config().api_key_prefix}{uuid.uuid4()}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt(rounds=get_config().bcrypt_rounds)).decode("utf-8")


def verify_api_key(api_key: str, api_key_hash: str) -> bool:
    """Validate a plaintext API key against a stored bcrypt hash."""
    return bcrypt.checkpw(api_key.encode("utf-8"), api_key_hash.encode("utf-8"))


def extract_bearer_token(authorization: str | None) -> str:
    """Extract a Bearer token from an Authorization header."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid Authorization header")
    return token


def authenticate_api_key(db: RelayDB, api_key: str) -> AgentContext:
    """Authenticate an API key against all stored bcrypt hashes."""
    for agent in db.get_agent_by_key_hashes():
        if verify_api_key(api_key, str(agent["api_key_hash"])):
            return AgentContext(agent_id=str(agent["agent_id"]), name=str(agent["name"]))
    # Constant-ish extra work to reduce obvious timing differences for empty registries.
    secrets.compare_digest(api_key, "")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


def current_db() -> RelayDB:
    """Return the configured relay database for non-HTTP paths."""
    if _db is None:
        raise RuntimeError("relay DB dependency not configured")
    return _db


async def get_db() -> RelayDB:
    """FastAPI dependency returning the configured relay database."""
    return current_db()


def set_db(db: RelayDB | None) -> None:
    """Set the relay database for FastAPI dependencies and websocket routes."""
    global _db
    _db = db


async def get_current_agent(
    authorization: str | None = Header(default=None),
    db: RelayDB = Depends(get_db),
) -> AgentContext:
    """FastAPI dependency that returns the authenticated agent."""
    return authenticate_api_key(db, extract_bearer_token(authorization))


def authenticate_websocket(db: RelayDB, websocket: WebSocket) -> AgentContext:
    """Authenticate a websocket connection from its api_key query param."""
    api_key = websocket.query_params.get("api_key")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing api_key")
    return authenticate_api_key(db, api_key)
