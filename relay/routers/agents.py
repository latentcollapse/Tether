"""Agent registry routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from relay.auth import AgentContext, generate_api_key, get_current_agent, get_db, hash_api_key
from relay.db import RelayDB
from relay.models import AgentInfo, AgentRegisterRequest, AgentRegisterResponse
from relay.routers.ws import manager

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(body: AgentRegisterRequest, db: RelayDB = Depends(get_db)) -> AgentRegisterResponse:
    """Register an agent and return its API key once."""
    api_key = generate_api_key()
    agent = db.create_agent(body.name, body.description, hash_api_key(api_key))
    return AgentRegisterResponse(agent_id=str(agent["agent_id"]), api_key=api_key)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> Response:
    """Delete the authenticated agent."""
    if current.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot delete another agent")
    db.delete_agent(agent_id)
    manager.disconnect(agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[AgentInfo])
async def list_agents(
    current: AgentContext = Depends(get_current_agent),
    db: RelayDB = Depends(get_db),
) -> list[AgentInfo]:
    """List relay agents."""
    _ = current
    return [
        AgentInfo(
            agent_id=str(row["agent_id"]),
            name=str(row["name"]),
            online=bool(row["online"]),
            last_seen=row.get("last_seen"),
        )
        for row in db.list_agents()
    ]
