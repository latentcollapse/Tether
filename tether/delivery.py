"""One authoritative backend path for durable Tether message delivery.

Storage, notification, prompt injection, submission, and application-level ACK
are different facts.  This module keeps them different while giving CLI, MCP,
and the dashboard the same typed outcome vocabulary.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DeliveryOutcome:
    handle: str
    to: str
    status: str
    mechanism: str
    prompt_state: str | None = None
    submitted: bool = False
    confirmed: bool = False
    held: bool = False
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["queued"] = self.status == "queued"
        result["notified"] = self.status in {"notified", "delivered"}
        result["delivered"] = self.status == "delivered"
        return result


def notice_line(*, to_agent: str, from_agent: str, subject: str, handle: str) -> str:
    """Return an inert, sender-independent wake instruction.

    The leading shell comment is defense in depth: even if every target guard
    fails and Enter reaches a shell, the wake cannot execute.  Subject, body,
    and sender are deliberately absent because they are untrusted message data.
    """
    if not re.fullmatch(r"h&l_[A-Za-z0-9_-]+_[A-Za-z0-9_-]+", handle or ""):
        raise ValueError("invalid Tether handle for prompt delivery")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", to_agent or ""):
        raise ValueError("invalid Tether agent id for prompt delivery")
    return f"# [Tether] resolve {handle} --agent {to_agent}"


def _persist(runtime, outcome: DeliveryOutcome) -> DeliveryOutcome:
    runtime.delivery_record(
        outcome.handle,
        outcome.to,
        outcome.status,
        outcome.mechanism,
        prompt_state=outcome.prompt_state,
        submitted=outcome.submitted,
        confirmed=outcome.confirmed,
        held=outcome.held,
        detail=outcome.detail,
    )
    return outcome


def _live_konsole_target(runtime, agent: str) -> dict | None:
    """Resolve a live target from current process identity, never cached state."""
    from tether import konsole_driver
    from tether.agent_config import load_agents

    if not konsole_driver.available():
        return None
    registry = load_agents()
    sessions = [session for session in konsole_driver.list_sessions() if not session.get("ambiguous")]
    for session in sessions:
        if konsole_driver.process_agent(session, registry) == agent:
            return session
    return None


def deliver_to_konsole(
    runtime,
    *,
    to_agent: str,
    from_agent: str,
    subject: str,
    handle: str,
    settle_seconds: float = 0.25,
    spawn_followup: bool = True,
) -> DeliveryOutcome:
    """Queue one handle; the singleton dispatcher is the only prompt writer."""
    notice_line(to_agent=to_agent, from_agent=from_agent, subject=subject, handle=handle)
    runtime.konsole_pending_add(handle, to_agent)
    try:
        from tether.delivery_worker import ensure_started
        ensure_started(runtime.db_path)
    except Exception as exc:
        runtime.delivery_attempt(handle, to_agent, "dispatcher", "start_failed", type(exc).__name__)
    return _persist(
        runtime,
        DeliveryOutcome(handle, to_agent, "queued", "database", detail="awaiting idle recipient"),
    )


def notify_message(
    runtime,
    *,
    to_agent: str,
    from_agent: str,
    subject: str,
    handle: str,
) -> DeliveryOutcome:
    """Persist work for the sole dispatcher; adapters never write prompts."""
    if not to_agent or to_agent == from_agent:
        return _persist(
            runtime,
            DeliveryOutcome(handle, to_agent, "queued", "database", detail="no external recipient"),
        )

    return deliver_to_konsole(
        runtime,
        to_agent=to_agent,
        from_agent=from_agent,
        subject=subject,
        handle=handle,
    )


def send_message(
    runtime,
    *,
    to_agent: str,
    subject: str,
    text: str,
    from_agent: str,
    tags: list[str] | None = None,
    ttl_seconds: int | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    value = {
        "from": from_agent,
        "to": to_agent,
        "subject": subject,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    handle = runtime.collapse(
        "messages",
        value,
        ttl_seconds=ttl_seconds,
        owner=to_agent,
        tags=tags,
        sender=from_agent,
        ticket_id=ticket_id,
    )
    outcome = notify_message(
        runtime,
        to_agent=to_agent,
        from_agent=from_agent,
        subject=subject,
        handle=handle,
    )
    result = outcome.to_dict()
    result["subject"] = subject
    if ttl_seconds is not None:
        result["ttl_seconds"] = int(ttl_seconds)
    return result
