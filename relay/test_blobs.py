import base64
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.tier import reset_daily_message_counts
from tether.crypto import build_encrypted_envelope, generate_keypair, resolve_encrypted_bytes


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


async def register(client: httpx.AsyncClient, name: str, pubkey: str | None = None) -> dict[str, str]:
    payload: dict[str, str] = {"name": name}
    if pubkey is not None:
        payload["pubkey"] = pubkey
    response = await client.post("/v1/agents/register", json=payload)
    assert response.status_code == 200
    return response.json()


def auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.anyio
async def test_uploader_can_store_and_fetch_blind_blob(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        public_key, private_key = generate_keypair()
        sender = await register(client, "sender", public_key)
        handle, data = build_encrypted_envelope("secret payload", public_key)

        uploaded = await client.post(
            "/v1/handles/blobs",
            headers=auth(sender["api_key"]),
            json={
                "handle": handle,
                "content_type": "application/vnd.tether.encrypted-envelope+json",
                "payload_b64": base64.b64encode(data).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200
        assert uploaded.json() == {"handle": handle, "stored": True}

        fetched = await client.get(f"/v1/handles/blobs/{handle}", headers=auth(sender["api_key"]))
        assert fetched.status_code == 200
        payload = fetched.json()
        assert resolve_encrypted_bytes(base64.b64decode(payload["payload_b64"]), private_key) == "secret payload"


@pytest.mark.anyio
async def test_recipient_can_fetch_blob_after_route(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        recipient_pubkey, recipient_privkey = generate_keypair()
        sender = await register(client, "sender")
        recipient = await register(client, "recipient", recipient_pubkey)
        handle, data = build_encrypted_envelope("hello over relay", recipient_pubkey)

        uploaded = await client.post(
            "/v1/handles/blobs",
            headers=auth(sender["api_key"]),
            json={
                "handle": handle,
                "content_type": "application/vnd.tether.encrypted-envelope+json",
                "payload_b64": base64.b64encode(data).decode("ascii"),
            },
        )
        assert uploaded.status_code == 200

        routed = await client.post(
            "/v1/handles/route",
            headers=auth(sender["api_key"]),
            json={"handle": handle, "to": recipient["agent_id"], "subject": "demo"},
        )
        assert routed.status_code == 200

        fetched = await client.get(f"/v1/handles/blobs/{handle}", headers=auth(recipient["api_key"]))
        assert fetched.status_code == 200
        payload = fetched.json()
        assert resolve_encrypted_bytes(base64.b64decode(payload["payload_b64"]), recipient_privkey) == "hello over relay"


@pytest.mark.anyio
async def test_unrelated_agent_cannot_fetch_blob(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        recipient_pubkey, _ = generate_keypair()
        sender = await register(client, "sender")
        recipient = await register(client, "recipient", recipient_pubkey)
        intruder = await register(client, "intruder")
        handle, data = build_encrypted_envelope("private", recipient_pubkey)

        await client.post(
            "/v1/handles/blobs",
            headers=auth(sender["api_key"]),
            json={
                "handle": handle,
                "content_type": "application/vnd.tether.encrypted-envelope+json",
                "payload_b64": base64.b64encode(data).decode("ascii"),
            },
        )
        await client.post(
            "/v1/handles/route",
            headers=auth(sender["api_key"]),
            json={"handle": handle, "to": recipient["agent_id"], "subject": "demo"},
        )

        fetched = await client.get(f"/v1/handles/blobs/{handle}", headers=auth(intruder["api_key"]))
        assert fetched.status_code == 403


@pytest.mark.anyio
async def test_duplicate_handle_with_same_payload_is_idempotent(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        recipient_pubkey, _ = generate_keypair()
        sender = await register(client, "sender")
        handle, data = build_encrypted_envelope("same payload", recipient_pubkey)
        body = {
            "handle": handle,
            "content_type": "application/vnd.tether.encrypted-envelope+json",
            "payload_b64": base64.b64encode(data).decode("ascii"),
        }

        first = await client.post("/v1/handles/blobs", headers=auth(sender["api_key"]), json=body)
        second = await client.post("/v1/handles/blobs", headers=auth(sender["api_key"]), json=body)

        assert first.json() == {"handle": handle, "stored": True}
        assert second.json() == {"handle": handle, "stored": False}
