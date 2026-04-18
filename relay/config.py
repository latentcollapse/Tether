"""Relay configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RelayConfig:
    """Environment-backed relay configuration."""

    host: str
    port: int
    db_path: str
    api_key_prefix: str
    bcrypt_rounds: int
    rate_limit_per_min: int
    stripe_webhook_secret: str | None
    stripe_price_duo: str | None
    stripe_price_basic: str | None
    stripe_price_pro: str | None
    stripe_secret_key: str | None


def get_config() -> RelayConfig:
    """Load relay configuration from environment variables."""
    return RelayConfig(
        host=os.environ.get("TETHER_RELAY_HOST", "0.0.0.0"),
        port=int(os.environ.get("TETHER_RELAY_PORT", "8000")),
        db_path=os.environ.get("TETHER_RELAY_DB", "./relay.db"),
        api_key_prefix=os.environ.get("TETHER_RELAY_KEY_PREFIX", "tk_live_"),
        bcrypt_rounds=int(os.environ.get("TETHER_RELAY_BCRYPT_ROUNDS", "12")),
        rate_limit_per_min=int(os.environ.get("TETHER_RATE_LIMIT_PER_MIN", "100")),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        stripe_price_duo=os.environ.get("STRIPE_PRICE_DUO"),
        stripe_price_basic=os.environ.get("STRIPE_PRICE_BASIC"),
        stripe_price_pro=os.environ.get("STRIPE_PRICE_PRO"),
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY"),
    )
