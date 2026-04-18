import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode

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
    response = await client.post("/v1/agents/register", json={"name": name, "description": f"{name} agent"})
    assert response.status_code == 200
    data = response.json()
    assert data["api_key"].startswith("tk_test_")
    return data


def auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


class AsgiWebSocket:
    def __init__(self, path: str) -> None:
        self.path = path
        self.to_app: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self.from_app: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self.task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        path, _, query = self.path.partition("?")
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query.encode("utf-8"),
            "headers": [],
            "scheme": "ws",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "subprotocols": [],
        }
        self.task = asyncio.create_task(app(scope, self.to_app.get, self.from_app.put))
        await self.to_app.put({"type": "websocket.connect"})
        accepted = await self.receive_event()
        assert accepted["type"] == "websocket.accept"

    async def send_json(self, data: dict[str, object]) -> None:
        await self.to_app.put({"type": "websocket.receive", "text": json.dumps(data)})

    async def receive_json(self) -> dict[str, object]:
        event = await self.receive_event()
        assert event["type"] == "websocket.send"
        return json.loads(str(event["text"]))

    async def receive_event(self) -> dict[str, object]:
        return await asyncio.wait_for(self.from_app.get(), timeout=0.5)

    async def close(self) -> None:
        await self.to_app.put({"type": "websocket.disconnect", "code": 1000})
        if self.task is not None:
            await asyncio.wait_for(self.task, timeout=0.5)


@pytest.mark.anyio
async def test_agent_register_list_and_delete(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        agent = await register(client, "codex")

        listed = await client.get("/v1/agents", headers=auth(agent["api_key"]))
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "agent_id": agent["agent_id"],
                "name": "codex",
                "online": False,
                "last_seen": listed.json()[0]["last_seen"],
                "tier": "teams",
            }
        ]

        deleted = await client.delete(f"/v1/agents/{agent['agent_id']}", headers=auth(agent["api_key"]))
        assert deleted.status_code == 204


@pytest.mark.anyio
async def test_route_to_offline_agent_queues(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await register(client, "sender")
        target = await register(client, "target")
        stored = relay_env.get_agent(sender["agent_id"])
        assert stored is not None
        assert stored["api_key_hash"] != sender["api_key"]

        routed = await client.post(
            "/v1/handles/route",
            headers=auth(sender["api_key"]),
            json={
                "handle": "h&l_inline_abc123",
                "to": target["agent_id"],
                "subject": "offline",
                "ticket_id": "T-020",
                "tags": ["relay"],
            },
        )

        assert routed.status_code == 200
        assert routed.json() == {"queued": True, "delivered": False}
        status = await client.get("/v1/handles/h&l_inline_abc123/status", headers=auth(sender["api_key"]))
        assert status.json() == {"handle": "h&l_inline_abc123", "status": "queued"}


@pytest.mark.anyio
async def test_websocket_receives_online_route(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await register(client, "sender")
        target = await register(client, "target")
        query = urlencode({"api_key": target["api_key"]})
        websocket = AsgiWebSocket(f"/v1/ws/{target['agent_id']}?{query}")
        await websocket.connect()
        try:
            await websocket.send_json({"type": "ping"})
            assert await websocket.receive_json() == {"type": "pong"}

            routed = await client.post(
                "/v1/handles/route",
                headers=auth(sender["api_key"]),
                json={"handle": "h&l_inline_live", "to": target["agent_id"], "subject": "live"},
            )

            assert routed.json() == {"queued": False, "delivered": True}
            pushed = await websocket.receive_json()
            assert pushed["type"] == "handle"
            assert pushed["handle"] == "h&l_inline_live"
            assert pushed["from"] == sender["agent_id"]
            assert pushed["subject"] == "live"
        finally:
            await websocket.close()


@pytest.mark.anyio
async def test_websocket_flushes_offline_queue_on_reconnect(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await register(client, "sender")
        target = await register(client, "target")
        routed = await client.post(
            "/v1/handles/route",
            headers=auth(sender["api_key"]),
            json={
                "handle": "h&l_tree_waiting",
                "to": target["agent_id"],
                "subject": "queued",
                "ticket_id": "T-020",
                "tags": ["offline"],
            },
        )
        assert routed.json() == {"queued": True, "delivered": False}

        query = urlencode({"api_key": target["api_key"]})
        websocket = AsgiWebSocket(f"/v1/ws/{target['agent_id']}?{query}")
        await websocket.connect()
        try:
            pushed = await websocket.receive_json()
            assert pushed["type"] == "handle"
            assert pushed["handle"] == "h&l_tree_waiting"
            assert pushed["ticket_id"] == "T-020"
            assert pushed["tags"] == ["offline"]
        finally:
            await websocket.close()

        status = await client.get("/v1/handles/h&l_tree_waiting/status", headers=auth(sender["api_key"]))
        assert status.json() == {"handle": "h&l_tree_waiting", "status": "delivered"}


@pytest.mark.anyio
async def test_health_reports_relay_mode(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["mode"] == "relay"
        assert payload["agents"] == 0
        assert isinstance(payload["dashboard"], bool)
