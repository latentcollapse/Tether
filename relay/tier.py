"""Relay subscription tier policy."""

from __future__ import annotations

import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from fastapi import HTTPException, status


class Tier(str, Enum):
    """Relay access tiers."""

    FREE = "free"
    TEAMS = "teams"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class TierFeatures:
    """Optional relay features enabled by tier."""

    encrypted_envelopes: bool
    pake_wan: bool


@dataclass(frozen=True)
class TierConfig:
    """Limits and features for a relay tier."""

    max_agents: int
    max_msg_per_day: int
    features: TierFeatures


DEFAULT_CONFIGS: dict[Tier, TierConfig] = {
    Tier.FREE: TierConfig(
        max_agents=0,
        max_msg_per_day=0,
        features=TierFeatures(encrypted_envelopes=False, pake_wan=False),
    ),
    Tier.TEAMS: TierConfig(
        max_agents=10,
        max_msg_per_day=5000,
        features=TierFeatures(encrypted_envelopes=False, pake_wan=False),
    ),
    Tier.ENTERPRISE: TierConfig(
        max_agents=-1,
        max_msg_per_day=-1,
        features=TierFeatures(encrypted_envelopes=True, pake_wan=True),
    ),
}

_daily_lock = threading.Lock()
_daily_message_counts: defaultdict[str, tuple[str, int]] = defaultdict(lambda: ("", 0))


def parse_tier(value: str) -> Tier:
    """Parse a tier string."""
    try:
        return Tier(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid tier") from exc


def current_utc_day() -> str:
    """Return the current UTC day key."""
    return datetime.now(timezone.utc).date().isoformat()


def tier_config(tier: Tier) -> TierConfig:
    """Return tier policy, applying Enterprise environment overrides."""
    if tier is not Tier.ENTERPRISE:
        return DEFAULT_CONFIGS[tier]

    base = DEFAULT_CONFIGS[Tier.ENTERPRISE]
    return TierConfig(
        max_agents=int(os.environ.get("TETHER_MAX_AGENTS", str(base.max_agents))),
        max_msg_per_day=int(os.environ.get("TETHER_MAX_MSG_PER_DAY", str(base.max_msg_per_day))),
        features=base.features,
    )


def registration_limit_config() -> tuple[Tier, TierConfig]:
    """Return the relay-wide registration tier limit."""
    if "TETHER_MAX_AGENTS" in os.environ:
        return Tier.ENTERPRISE, tier_config(Tier.ENTERPRISE)
    return Tier.TEAMS, tier_config(Tier.TEAMS)


def reset_daily_message_counts() -> None:
    """Clear in-memory daily message counters."""
    with _daily_lock:
        _daily_message_counts.clear()


def message_limit_response(tier: Tier, limit: int) -> dict[str, object]:
    """Build the standardized message limit response body."""
    return {
        "error": "rate_limit_exceeded",
        "tier": tier.value,
        "limit": limit,
        "upgrade": "set TETHER_MAX_MSG_PER_DAY or upgrade tier",
    }


def agent_limit_response(tier: Tier, max_agents: int) -> dict[str, object]:
    """Build the standardized agent limit response body."""
    return {"error": "agent_limit_reached", "tier": tier.value, "max_agents": max_agents}


def record_message_or_response(agent_id: str, tier: Tier) -> dict[str, object] | None:
    """Increment daily message usage or return a 429 response body."""
    config = tier_config(tier)
    limit = config.max_msg_per_day
    if limit < 0:
        return None

    today = current_utc_day()
    with _daily_lock:
        day, count = _daily_message_counts[agent_id]
        if day != today:
            day = today
            count = 0
        if count >= limit:
            _daily_message_counts[agent_id] = (day, count)
            return message_limit_response(tier, limit)
        _daily_message_counts[agent_id] = (day, count + 1)
    return None
