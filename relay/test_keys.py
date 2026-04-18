from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.tier import reset_daily_message_counts


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


async def issue_key(
    client: httpx.AsyncClient,
    agent_id: str,
    api_key: str,
    label: str | None = None,
) -> dict[str, str]:
    response = await client.post(
        "/v1/keys",
        headers=auth(api_key),
        json={"agent_id": agent_id, "label": label},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == agent_id
    assert data["api_key"].startswith("tk_test_")
    return data


@pytest.mark.anyio
async def test_issue_key_and_use_it(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        issued = await issue_key(client, agent["agent_id"], agent["api_key"], "laptop")

        listed = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        assert listed.status_code == 200
        stored = relay_env.get_key(issued["key_id"])
        assert stored is not None
        assert stored["key_hash"] != issued["api_key"]


@pytest.mark.anyio
async def test_revoke_key_rejects_future_auth(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        issued = await issue_key(client, agent["agent_id"], agent["api_key"])

        revoked = await client.delete(f"/v1/keys/{issued['key_id']}", headers=auth(agent["api_key"]))
        assert revoked.status_code == 204

        listed = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        assert listed.status_code == 401


@pytest.mark.anyio
async def test_rotate_key_revokes_old_and_issues_new(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        issued = await issue_key(client, agent["agent_id"], agent["api_key"])

        rotated = await client.post(f"/v1/keys/{issued['key_id']}/rotate", headers=auth(issued["api_key"]))
        assert rotated.status_code == 200
        replacement = rotated.json()
        assert replacement["new_key_id"] != issued["key_id"]
        assert replacement["api_key"].startswith("tk_test_")

        old_auth = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        assert old_auth.status_code == 401
        new_auth = await client.get("/v1/agents", headers=auth(replacement["api_key"]))
        assert new_auth.status_code == 200


@pytest.mark.anyio
async def test_list_keys_omits_plaintext_and_hashes(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        first = await issue_key(client, agent["agent_id"], agent["api_key"], "first")
        second = await issue_key(client, agent["agent_id"], agent["api_key"], "second")

        listed = await client.get("/v1/keys", headers=auth(agent["api_key"]))
        assert listed.status_code == 200
        keys = listed.json()
        assert {row["key_id"] for row in keys} == {first["key_id"], second["key_id"]}
        assert {row["label"] for row in keys} == {"first", "second"}
        assert all("api_key" not in row for row in keys)
        assert all("key_hash" not in row for row in keys)


@pytest.mark.anyio
async def test_rate_limit_returns_429(relay_env: RelayDB, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_RATE_LIMIT_PER_MIN", "2")
    relay_auth.reset_rate_limits()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")
        issued = await issue_key(client, agent["agent_id"], agent["api_key"])

        first = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        second = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        limited = await client.get("/v1/agents", headers=auth(issued["api_key"]))

        assert first.status_code == 200
        assert second.status_code == 200
        assert limited.status_code == 429
        assert int(limited.headers["Retry-After"]) > 0


@pytest.mark.anyio
async def test_wrong_owner_cannot_revoke_key(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        owner = await register(client, "owner")
        other = await register(client, "other")
        issued = await issue_key(client, owner["agent_id"], owner["api_key"])

        revoked = await client.delete(f"/v1/keys/{issued['key_id']}", headers=auth(other["api_key"]))
        assert revoked.status_code == 403

        still_valid = await client.get("/v1/agents", headers=auth(issued["api_key"]))
        assert still_valid.status_code == 200
