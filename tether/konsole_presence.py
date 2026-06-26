#!/usr/bin/env python3
"""
Tether Konsole presence reconcile loop — keeps live agent state true to reality.

The Network Graph problem: agents that run as CLIs in Konsole tabs (claude, codex, …)
never send presence heartbeats, so `tether_presence` goes stale and shows them offline,
while the graph's old source (`/api/agents`) inferred "online" from message *history* —
so retired/idle agents with chat history showed online and genuinely-live agents with no
recent messages were invisible. Neither reflected who is actually connected.

This loop makes presence the live source of truth for Konsole agents. Every tick it:
  - scans the live Konsole tabs (foreground process resolves → the tab is alive)
  - matches each to a registry agent (`guess_agent`)
  - binds newly-appeared agents (continuous autowire — not just one-shot at startup),
    points their ping URL at this dashboard's konsole_deliver endpoint
  - heartbeats every live bound agent so presence stays "online" (the heartbeat surrogate
    Konsole agents otherwise lack)
  - marks agents whose bound tab has vanished offline and unbinds them

`/ws/agents` already pushes `presence_list()` every 5s, so once presence is accurate the
graph reflects reality with no further backend change. Runs as a daemon thread in the
dashboard process. Best-effort — a tick failure never crashes the server.
"""
import logging
import threading

logger = logging.getLogger(__name__)

RECONCILE_INTERVAL_SECONDS = 5  # < presence_list stale window (15s) so live agents never flap offline


def reconcile_once(db_path: str, port: int) -> list[str]:
    """One reconcile pass. Returns the list of agents confirmed live this tick."""
    try:
        from tether import konsole_driver
    except Exception:
        return []
    if not konsole_driver.available():
        return []
    try:
        from tether.agent_config import load_agents
        registry = load_agents()
    except Exception:
        registry = []

    from tether.sqlite_runtime import SQLiteRuntime
    rt = SQLiteRuntime(db_path=db_path)
    live: list[str] = []
    try:
        # Discover live Konsole agents (a session in list_sessions has a live foreground proc).
        seen: dict[str, dict] = {}
        for s in konsole_driver.list_sessions():
            if s.get("ambiguous"):
                continue
            agent = konsole_driver.guess_agent(s, registry)
            if agent and agent not in seen:
                seen[agent] = s

        bound = {b["agent"]: b for b in rt.konsole_bindings()}

        # Bind/refresh + heartbeat everything currently live.
        for agent, s in seen.items():
            try:
                cur = bound.get(agent)
                if not cur or cur.get("session") != s["session"] or cur.get("service") != s["service"]:
                    konsole_driver.set_title(s["service"], s["session"], agent)
                    rt.konsole_bind(agent, s["service"], s["session"])
                    rt.set_ping_url(agent, f"http://localhost:{port}/api/konsole/deliver?agent={agent}")
                rt.presence_register(agent)  # upserts status=online with a fresh heartbeat
                live.append(agent)
            except Exception:
                continue  # one bad tab must not abort the pass

        # Anything bound but no longer live → offline + unbind (its tab closed).
        for agent in bound:
            if agent not in seen:
                try:
                    rt.presence_offline(agent)
                    rt.konsole_unbind(agent)
                except Exception:
                    continue
    finally:
        rt.close()
    return live


def _loop(db_path: str, port: int, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            reconcile_once(db_path, port)
        except Exception:
            logger.exception("konsole presence reconcile pass failed")
        stop_event.wait(RECONCILE_INTERVAL_SECONDS)


def start(db_path: str, port: int) -> threading.Event:
    """Start the reconcile loop as a daemon thread. Returns the stop Event."""
    stop_event = threading.Event()
    threading.Thread(target=_loop, args=(db_path, port, stop_event), daemon=True).start()
    logger.info("konsole presence reconcile loop started (interval=%ds)", RECONCILE_INTERVAL_SECONDS)
    return stop_event
