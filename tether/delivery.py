"""One authoritative backend path for durable Tether message delivery.

Storage, notification, prompt injection, submission, and application-level ACK
are different facts.  This module keeps them different while giving CLI, MCP,
and the dashboard the same typed outcome vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
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
    short_subject = " ".join(subject.split())
    if len(short_subject) > 120:
        short_subject = short_subject[:117] + "..."
    return (
        f"[Tether] New message from {from_agent}: {short_subject} "
        f"— run `tether resolve '{handle}' --agent {to_agent}`"
    )


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


def _spawn_followup(*, service: str, session: str, handle: str, agent: str, db_path: str) -> None:
    """Detach the exact-handle waiter from a short-lived sender process."""
    command = [
        sys.executable,
        "-m",
        "tether.konsole_followup",
        "--service",
        service,
        "--session",
        session,
        "--handle",
        handle,
        "--agent",
        agent,
        "--db",
        db_path,
    ]
    unit = "tether-followup-" + hashlib.sha256(handle.encode("utf-8")).hexdigest()[:16]
    try:
        result = subprocess.run(
            ["systemd-run", "--user", "--quiet", "--collect", f"--unit={unit}", *command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


def _live_konsole_target(runtime, agent: str) -> dict | None:
    """Return a live, correctly identified tab and repair stale bindings."""
    from tether import konsole_driver
    from tether.agent_config import load_agents

    if not konsole_driver.available():
        return None
    registry = load_agents()
    sessions = [session for session in konsole_driver.list_sessions() if not session.get("ambiguous")]
    binding = runtime.konsole_binding(agent)
    if binding:
        bound = next(
            (
                session
                for session in sessions
                if session.get("service") == binding["service"]
                and session.get("session") == binding["session"]
            ),
            None,
        )
        if bound is not None and konsole_driver.guess_agent(bound, registry) == agent:
            return bound
        runtime.konsole_unbind(agent)

    for session in sessions:
        if konsole_driver.guess_agent(session, registry) == agent:
            runtime.konsole_bind(agent, session["service"], session["session"])
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
    """Place one durable notice in the recipient's prompt without clobbering input."""
    from tether import konsole_driver

    line = notice_line(
        to_agent=to_agent,
        from_agent=from_agent,
        subject=subject,
        handle=handle,
    )
    target = _live_konsole_target(runtime, to_agent)
    if target is None:
        runtime.delivery_attempt(handle, to_agent, "konsole", "no_live_target")
        return _persist(
            runtime,
            DeliveryOutcome(handle, to_agent, "queued", "database", detail="no live Konsole target"),
        )

    # Register before touching the PTY.  A crash after sendText can therefore
    # never create an untracked notification.
    runtime.konsole_pending_add(handle, to_agent, line)
    ok, state = konsole_driver.inject_tether_notice(target["service"], target["session"], line)
    runtime.delivery_attempt(handle, to_agent, "konsole", "injected" if ok else "rejected", state)
    if not ok:
        return _persist(
            runtime,
            DeliveryOutcome(
                handle,
                to_agent,
                "undeliverable",
                "konsole",
                prompt_state=state,
                detail="Konsole D-Bus rejected sendText",
            ),
        )

    if settle_seconds:
        time.sleep(settle_seconds)
    in_composer = konsole_driver.composer_contains(target["service"], target["session"], handle)
    visible = konsole_driver.screen_contains(target["service"], target["session"], handle)

    if state == "empty":
        # inject_tether_notice submitted only after positively identifying an
        # empty composer.  Visibility is useful confirmation but not required:
        # fast TUIs can consume and scroll the line before the readback.
        runtime.konsole_pending_resolve(handle, to_agent, "delivered")
        return _persist(
            runtime,
            DeliveryOutcome(
                handle,
                to_agent,
                "delivered",
                "konsole",
                prompt_state=state,
                submitted=True,
                confirmed=visible,
                detail="submitted from positively empty prompt",
            ),
        )

    # Nonempty/unknown prompts receive bytes but never Enter.  Confirm current
    # composer ownership separately from generic transcript visibility.
    held = state in {"draft", "busy", "unknown"}
    status = "delivered" if in_composer else "notified"
    outcome = _persist(
        runtime,
        DeliveryOutcome(
            handle,
            to_agent,
            status,
            "konsole",
            prompt_state=state,
            submitted=False,
            confirmed=in_composer,
            held=held,
            detail=(
                "notice held in current prompt; human input remains in control"
                if in_composer
                else "D-Bus accepted notice; prompt ownership awaiting confirmation"
            ),
        ),
    )
    runtime.konsole_pending_defer(handle, to_agent, interval_seconds=1)
    # The waiter is allowed to submit only a Tether-owned composer, never a
    # mixed human draft.  Starting it for every held state also provides ACK
    # cleanup when the original state was conservatively unknown.
    if spawn_followup:
        _spawn_followup(
            service=target["service"],
            session=target["session"],
            handle=handle,
            agent=to_agent,
            db_path=runtime.db_path,
        )
    return outcome


def _post_http(url: str, payload: dict) -> dict | None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        raw = response.read()
    if not raw:
        return None
    decoded = json.loads(raw.decode("utf-8"))
    return decoded if isinstance(decoded, dict) else None


def notify_message(
    runtime,
    *,
    to_agent: str,
    from_agent: str,
    subject: str,
    handle: str,
) -> DeliveryOutcome:
    """Run the prompt-first delivery ladder and return its truthful outcome."""
    if not to_agent or to_agent == from_agent:
        return _persist(
            runtime,
            DeliveryOutcome(handle, to_agent, "queued", "database", detail="no external recipient"),
        )

    direct = deliver_to_konsole(
        runtime,
        to_agent=to_agent,
        from_agent=from_agent,
        subject=subject,
        handle=handle,
    )
    if direct.status in {"notified", "delivered"}:
        return direct

    ping_url = runtime.get_ping_url(to_agent)
    if ping_url:
        payload = {
            "event": "tether_message",
            "to": to_agent,
            "from": from_agent,
            "subject": subject,
            "handle": handle,
        }
        try:
            response = _post_http(ping_url, payload)
            accepted = bool(response and response.get("ok") and response.get("injected"))
            runtime.delivery_attempt(
                handle,
                to_agent,
                "http",
                "accepted" if accepted else "rejected",
                json.dumps(response, sort_keys=True) if response is not None else "empty response",
            )
            if accepted:
                response_status = str(response.get("status") or "")
                if response_status not in {"queued", "notified", "delivered", "undeliverable"}:
                    response_status = "delivered" if response.get("delivered") else "notified"
                outcome = DeliveryOutcome(
                    handle,
                    to_agent,
                    response_status,
                    "http",
                    prompt_state=response.get("prompt_state"),
                    submitted=bool(response.get("submitted")),
                    confirmed=bool(response.get("confirmed") or response.get("delivered")),
                    held=bool(response.get("held")),
                    detail="live receiver accepted prompt delivery",
                )
                return _persist(runtime, outcome)
        except Exception as exc:
            runtime.delivery_attempt(handle, to_agent, "http", "failed", type(exc).__name__)

    # The database remains authoritative and unread recovery can still surface
    # the message at the next agent boundary.  A passive breadcrumb is useful,
    # but it is never mislabeled as prompt delivery.
    try:
        notify_path = os.path.join(os.path.expanduser("~"), ".tether_notify")
        with open(notify_path, "w", encoding="utf-8") as file:
            file.write(f"{handle} | {from_agent}: {subject}")
        runtime.delivery_attempt(handle, to_agent, "notify_file", "written")
    except OSError as exc:
        runtime.delivery_attempt(handle, to_agent, "notify_file", "failed", type(exc).__name__)

    if direct.status == "undeliverable":
        return _persist(runtime, direct)
    return _persist(
        runtime,
        DeliveryOutcome(handle, to_agent, "queued", "database", detail="awaiting a live prompt target"),
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
