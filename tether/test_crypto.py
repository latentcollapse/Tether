import base64
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from nacl.public import PrivateKey, PublicKey

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.tier import reset_daily_message_counts
from tether.crypto import collapse_encrypted, generate_keypair, resolve_encrypted
from tether.handles import BLOB_PREFIX, kvfold_dir, suffix


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


def test_generate_keypair_returns_base64_x25519_material() -> None:
    public_key, private_key = generate_keypair()

    assert len(base64.b64decode(public_key)) == PublicKey.SIZE
    assert len(base64.b64decode(private_key)) == PrivateKey.SIZE


def test_encrypt_decrypt_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    public_key, private_key = generate_keypair()

    handle = collapse_encrypted("top secret payload", public_key)

    assert handle.startswith(BLOB_PREFIX)
    assert resolve_encrypted(handle, private_key) == "top secret payload"


def test_wrong_private_key_raises_decryption_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    public_key, _ = generate_keypair()
    _, wrong_private_key = generate_keypair()
    handle = collapse_encrypted("classified", public_key)

    with pytest.raises(ValueError, match="failed to decrypt encrypted envelope"):
        resolve_encrypted(handle, wrong_private_key)


def test_intercepted_envelope_contains_only_ciphertext(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    public_key, private_key = generate_keypair()
    plaintext = "relay should not see this"

    handle = collapse_encrypted(plaintext, public_key)
    raw = (kvfold_dir(tmp_path / "kvfold") / suffix(handle, BLOB_PREFIX)).read_bytes()
    envelope = json.loads(raw.decode("utf-8"))

    assert plaintext.encode("utf-8") not in raw
    assert set(envelope) == {"encrypted_payload", "ephemeral_pubkey", "nonce"}
    assert envelope["encrypted_payload"] != base64.b64encode(plaintext.encode("utf-8")).decode("ascii")
    assert resolve_encrypted(handle, private_key) == plaintext


async def _register(client: httpx.AsyncClient, name: str, pubkey: str | None = None) -> dict[str, str]:
    payload: dict[str, str] = {"name": name}
    if pubkey is not None:
        payload["pubkey"] = pubkey
    response = await client.post("/v1/agents/register", json=payload)
    assert response.status_code == 200
    return response.json()


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.anyio
async def test_pubkey_route_requires_enterprise_tier(
    relay_env: RelayDB,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    public_key, _ = generate_keypair()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await _register(client, "sender")
        recipient = await _register(client, "recipient", public_key)

        response = await client.get(
            f"/v1/agents/{recipient['agent_id']}/pubkey",
            headers=_auth(sender["api_key"]),
        )

        assert response.status_code == 403
        assert response.json() == {
            "error": "upgrade_required",
            "tier": "teams",
            "feature": "encrypted_envelopes",
            "upgrade": "upgrade tier for encrypted_envelopes",
        }


@pytest.mark.anyio
async def test_enterprise_agents_can_fetch_pubkey(
    relay_env: RelayDB,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TETHER_KVFOLD_DIR", str(tmp_path / "kvfold"))
    public_key, _ = generate_keypair()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sender = await _register(client, "sender")
        recipient = await _register(client, "recipient", public_key)
        relay_env.set_agent_tier(sender["agent_id"], "enterprise")
        relay_env.set_agent_tier(recipient["agent_id"], "enterprise")

        response = await client.get(
            f"/v1/agents/{recipient['agent_id']}/pubkey",
            headers=_auth(sender["api_key"]),
        )

        assert response.status_code == 200
        assert response.json() == {"agent_id": recipient["agent_id"], "pubkey": public_key}
