"""Stripe-backed relay billing routes."""

from __future__ import annotations

import hmac
import json
import logging
from hashlib import sha256
from urllib import error, request

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from relay.auth import generate_api_key, get_db, hash_api_key
from relay.config import get_config
from relay.db import RelayDB
from relay.models import BillingKeyResponse, BillingResendRequest, BillingResendResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["billing"])


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: RelayDB = Depends(get_db),
) -> dict[str, object]:
    """Process Stripe subscription lifecycle events."""
    config = get_config()
    if not config.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="stripe webhook secret is not configured")
    raw = await request.body()
    verify_stripe_signature(raw, stripe_signature, config.stripe_webhook_secret)
    event = json.loads(raw.decode("utf-8"))
    event_id = str(event.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing Stripe event id")
    if db.is_billing_event_processed(event_id):
        return {"received": True, "duplicate": True}
    process_stripe_event(db, config, event)
    return {"received": True, "duplicate": False}


@router.get("/billing/key", response_model=BillingKeyResponse)
async def billing_key(
    session_id: str = Query(min_length=1),
    db: RelayDB = Depends(get_db),
) -> BillingKeyResponse:
    """Issue a customer API key once after Stripe Checkout redirect."""
    config = get_config()
    if not config.stripe_secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="stripe secret key is not configured")
    session = fetch_checkout_session(config.stripe_secret_key, session_id)
    stripe_customer_id = str(session.get("customer") or "")
    email = checkout_session_email(session)
    if not stripe_customer_id or not email:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe session missing customer/email")

    customer = db.get_customer_by_stripe_customer_id(stripe_customer_id) or db.get_customer_by_email(email)
    if customer is None:
        customer = db.upsert_customer(stripe_customer_id, email, str(session.get("tier") or "free"))
    if customer.get("api_key_hash"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Key already issued. Check your email.")

    api_key = generate_api_key()
    db.set_customer_api_key_hash(str(customer["id"]), hash_api_key(api_key))
    fresh = db.get_customer_by_id(str(customer["id"]))
    if fresh is None:
        raise RuntimeError("customer vanished after key issuance")
    return BillingKeyResponse(api_key=api_key, customer_id=str(fresh["id"]), tier=str(fresh["tier"]))


@router.post("/billing/resend-key", response_model=BillingResendResponse)
async def resend_key(
    body: BillingResendRequest,
    db: RelayDB = Depends(get_db),
) -> BillingResendResponse:
    """Placeholder resend flow that avoids emailing key material."""
    customer = db.get_customer_by_email(body.email)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    logger.info("billing resend requested", extra={"email": body.email, "customer_id": customer["id"]})
    return BillingResendResponse(status="queued")


def verify_stripe_signature(payload: bytes, signature_header: str | None, secret: str) -> None:
    """Validate Stripe's webhook signature header."""
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing Stripe-Signature")
    parts = dict(part.split("=", 1) for part in signature_header.split(",") if "=" in part)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid Stripe-Signature")
    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid Stripe signature")


def process_stripe_event(db: RelayDB, config: object, event: dict[str, object]) -> None:
    """Persist Stripe subscription state idempotently."""
    event_id = str(event.get("id") or "")
    if not event_id or db.is_billing_event_processed(event_id):
        return
    event_type = str(event.get("type") or "")
    obj = event.get("data", {})
    payload = obj.get("object", {}) if isinstance(obj, dict) else {}
    stripe_customer_id = str(payload.get("customer") or "")
    email = subscription_email(payload)
    if not stripe_customer_id or not email:
        db.mark_billing_event_processed(event_id)
        return
    if event_type == "customer.subscription.deleted":
        tier = "free"
    else:
        tier = price_id_to_tier(getattr(config, "stripe_price_duo", None), getattr(config, "stripe_price_basic", None), getattr(config, "stripe_price_pro", None), subscription_price_id(payload))
    db.upsert_customer(stripe_customer_id, email, tier)
    db.mark_billing_event_processed(event_id)


def subscription_price_id(subscription: dict[str, object]) -> str | None:
    """Extract the first subscription price id from a Stripe event payload."""
    items = subscription.get("items", {})
    data = items.get("data", []) if isinstance(items, dict) else []
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if not isinstance(first, dict):
        return None
    price = first.get("price", {})
    if not isinstance(price, dict):
        return None
    raw = price.get("id")
    return str(raw) if raw else None


def subscription_email(subscription: dict[str, object]) -> str | None:
    """Extract a billing email from a subscription object."""
    for key in ("customer_email", "email"):
        value = subscription.get(key)
        if value:
            return str(value)
    metadata = subscription.get("metadata", {})
    if isinstance(metadata, dict):
        value = metadata.get("email")
        if value:
            return str(value)
    return None


def checkout_session_email(session: dict[str, object]) -> str | None:
    """Extract a billing email from a Stripe Checkout session."""
    details = session.get("customer_details", {})
    if isinstance(details, dict) and details.get("email"):
        return str(details["email"])
    email = session.get("customer_email")
    return str(email) if email else None


def price_id_to_tier(price_duo: str | None, price_basic: str | None, price_pro: str | None, price_id: str | None) -> str:
    """Map a Stripe price id to a customer tier string."""
    if price_id and price_duo and price_id == price_duo:
        return "duo"
    if price_id and price_basic and price_id == price_basic:
        return "basic"
    if price_id and price_pro and price_id == price_pro:
        return "pro"
    return "free"


def fetch_checkout_session(secret_key: str, session_id: str) -> dict[str, object]:
    """Fetch a Stripe Checkout session over HTTPS."""
    req = request.Request(
        f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
        headers={"Authorization": f"Bearer {secret_key}"},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Stripe lookup failed: {detail}") from exc
