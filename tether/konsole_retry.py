"""Compatibility facade for the retired v2 retry scheduler.

Delivery now belongs exclusively to :mod:`tether.delivery_worker`.
"""

import threading


def process_due(runtime, agent_filter: str | None = None) -> dict:
    from tether.delivery_worker import process_once

    if agent_filter is not None:
        # The new dispatcher is intentionally global and already limits work to
        # one handle per recipient per tick. Scoped workers no longer exist.
        return {"delivered": 0, "waiting": 0, "missing": 0}
    return process_once(runtime)


def start(db_path: str, agent: str | None = None) -> threading.Event:
    from tether.delivery_worker import ensure_started

    if agent is None:
        ensure_started(db_path)
    return threading.Event()
