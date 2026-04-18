"""Pydantic models for the Tether relay API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class AgentRegisterResponse(BaseModel):
    agent_id: str
    api_key: str


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    online: bool
    last_seen: str | None
    tier: str


class RouteHandleRequest(BaseModel):
    handle: str = Field(min_length=1)
    to: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    ticket_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class RouteHandleResponse(BaseModel):
    queued: bool
    delivered: bool


class HandleStatusResponse(BaseModel):
    handle: str
    status: str


class KeyCreateRequest(BaseModel):
    agent_id: str = Field(min_length=1)
    label: str | None = None


class KeyCreateResponse(BaseModel):
    key_id: str
    api_key: str
    agent_id: str
    created_at: str


class KeyRotateResponse(BaseModel):
    new_key_id: str
    api_key: str


class KeyInfo(BaseModel):
    key_id: str
    agent_id: str
    label: str | None
    created_at: str
    revoked_at: str | None


class AdminTierRequest(BaseModel):
    tier: str


class AdminTierResponse(BaseModel):
    agent_id: str
    tier: str


class HandlePush(BaseModel):
    type: str = "handle"
    handle: str
    from_agent: str = Field(alias="from")
    subject: str
    ticket_id: str | None
    tags: list[str]
    timestamp: str

    model_config = {"populate_by_name": True}
