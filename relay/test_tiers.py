from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.tier import DEFAULT_CONFIGS, Tier, reset_daily_message_counts


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def relay_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[RelayDB]:
    db_path = tmp_path / "relay.db"
    monkeypatch.setenv("TETHER_RELAY_DB", str(db_path))
    monkeypatch.setenv("TETHER_RELAY_KEY_PREFIX", "tk_test_")
    monkeypatch.setenv("TETHER_RELAY_BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("TETHER_RATE_LIMIT_PER_MIN", "100")
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db = RelayDB(str(db_path))
    relay_auth.set_db(db)
    yield db
    relay_auth.set_db(None)
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db.close()


async def register(client: httpx.AsyncClient, name: str) -> dict[str, str]:
    response = await client.post("/v1/agents/register", json={"name": name})
    assert response.status_code == 200
    return response.json()


def auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


async def route_handle(
    client: httpx.AsyncClient,
    sender: dict[str, str],
    target: dict[str, str],
    handle: str,
) -> httpx.Response:
    return await client.post(
        "/v1/handles/route",
        headers=auth(sender["api_key"]),
        json={"handle": handle, "to": target["agent_id"], "subject": "tier-check"},
    )


@pytest.mark.anyio
async def test_teams_agent_hits_message_limit(
    relay_env: RelayDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        DEFAULT_CONFIGS,
        Tier.TEAMS,
        replace(DEFAULT_CONFIGS[Tier.TEAMS], max_msg_per_day=1),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await register(client, "sender")
        target = await register(client, "target")

        first = await route_handle(client, sender, target, "h&l_inline_one")
        second = await route_handle(client, sender, target, "h&l_inline_two")

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json() == {
            "error": "rate_limit_exceeded",
            "tier": "teams",
            "limit": 1,
            "upgrade": "set TETHER_MAX_MSG_PER_DAY or upgrade tier",
        }


@pytest.mark.anyio
async def test_teams_relay_hits_agent_limit(
    relay_env: RelayDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        DEFAULT_CONFIGS,
        Tier.TEAMS,
        replace(DEFAULT_CONFIGS[Tier.TEAMS], max_agents=1),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v1/agents/register", json={"name": "first"})
        second = await client.post("/v1/agents/register", json={"name": "second"})

        assert first.status_code == 200
        assert second.status_code == 403
        assert second.json() == {"error": "agent_limit_reached", "tier": "teams", "max_agents": 1}


@pytest.mark.anyio
async def test_enterprise_agent_limit_can_be_unlimited(
    relay_env: RelayDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TETHER_MAX_AGENTS", "-1")
    monkeypatch.setitem(
        DEFAULT_CONFIGS,
        Tier.TEAMS,
        replace(DEFAULT_CONFIGS[Tier.TEAMS], max_agents=1),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.post("/v1/agents/register", json={"name": f"agent-{index}"})
            for index in range(12)
        ]

        assert all(response.status_code == 200 for response in responses)


@pytest.mark.anyio
async def test_admin_upgrade_changes_limits_immediately(
    relay_env: RelayDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TETHER_ADMIN_KEY", "admin-secret")
    monkeypatch.setenv("TETHER_MAX_MSG_PER_DAY", "-1")
    monkeypatch.setitem(
        DEFAULT_CONFIGS,
        Tier.TEAMS,
        replace(DEFAULT_CONFIGS[Tier.TEAMS], max_msg_per_day=1),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await register(client, "sender")
        target = await register(client, "target")

        first = await route_handle(client, sender, target, "h&l_inline_before")
        limited = await route_handle(client, sender, target, "h&l_inline_limited")
        upgraded = await client.post(
            f"/v1/admin/agents/{sender['agent_id']}/tier",
            headers=auth("admin-secret"),
            json={"tier": "enterprise"},
        )
        after_upgrade = await route_handle(client, sender, target, "h&l_inline_after")

        assert first.status_code == 200
        assert limited.status_code == 429
        assert upgraded.status_code == 200
        assert upgraded.json() == {"agent_id": sender["agent_id"], "tier": "enterprise"}
        assert after_upgrade.status_code == 200


@pytest.mark.anyio
async def test_wrong_admin_key_returns_401(
    relay_env: RelayDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TETHER_ADMIN_KEY", "admin-secret")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        response = await client.post(
            f"/v1/admin/agents/{agent['agent_id']}/tier",
            headers=auth("wrong-secret"),
            json={"tier": "enterprise"},
        )

        assert response.status_code == 401


@pytest.mark.anyio
async def test_missing_admin_key_returns_503(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        response = await client.post(
            f"/v1/admin/agents/{agent['agent_id']}/tier",
            headers=auth("admin-secret"),
            json={"tier": "enterprise"},
        )

        assert response.status_code == 503
