import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.routers import billing
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
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_PRICE_DUO", "price_duo")
    monkeypatch.setenv("STRIPE_PRICE_BASIC", "price_basic")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db = RelayDB(str(db_path))
    relay_auth.set_db(db)
    yield db
    relay_auth.set_db(None)
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db.close()


def sign(payload: bytes, secret: str = "whsec_test") -> str:
    return billing.hmac.new(secret.encode("utf-8"), b"12345." + payload, billing.sha256).hexdigest()


@pytest.mark.anyio
async def test_webhook_with_valid_signature_updates_tier(relay_env: RelayDB) -> None:
    payload = {
        "id": "evt_1",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "customer": "cus_123",
                "customer_email": "buyer@example.com",
                "items": {"data": [{"price": {"id": "price_basic"}}]},
            }
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": f"t=12345,v1={sign(raw)}"})
        assert response.status_code == 200
        customer = relay_env.get_customer_by_stripe_customer_id("cus_123")
        assert customer is not None
        assert customer["tier"] == "basic"


@pytest.mark.anyio
async def test_webhook_with_invalid_signature_returns_400(relay_env: RelayDB) -> None:
    raw = json.dumps({"id": "evt_bad", "type": "customer.subscription.created", "data": {"object": {}}}).encode("utf-8")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": "t=12345,v1=bad"})
        assert response.status_code == 400


@pytest.mark.anyio
async def test_duplicate_event_id_is_idempotent(relay_env: RelayDB) -> None:
    payload = {
        "id": "evt_dup",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "customer": "cus_dup",
                "customer_email": "dup@example.com",
                "items": {"data": [{"price": {"id": "price_duo"}}]},
            }
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": f"t=12345,v1={sign(raw)}"})
        second = await client.post("/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": f"t=12345,v1={sign(raw)}"})
        assert first.json() == {"received": True, "duplicate": False}
        assert second.json() == {"received": True, "duplicate": True}


@pytest.mark.anyio
async def test_billing_key_returns_key_once(relay_env: RelayDB, monkeypatch: pytest.MonkeyPatch) -> None:
    relay_env.upsert_customer("cus_checkout", "buyer@example.com", "basic")
    monkeypatch.setattr(
        billing,
        "fetch_checkout_session",
        lambda secret_key, session_id: {
            "customer": "cus_checkout",
            "customer_details": {"email": "buyer@example.com"},
        },
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/v1/billing/key", params={"session_id": "cs_test"})
        second = await client.get("/v1/billing/key", params={"session_id": "cs_test"})

        assert first.status_code == 200
        body = first.json()
        assert body["api_key"].startswith("tk_test_")
        assert body["tier"] == "basic"
        assert second.status_code == 409


@pytest.mark.anyio
async def test_billing_resend_key_logs_placeholder(relay_env: RelayDB) -> None:
    relay_env.upsert_customer("cus_resend", "buyer@example.com", "duo")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/billing/resend-key", json={"email": "buyer@example.com"})
        assert response.status_code == 200
        assert response.json() == {"status": "queued"}
