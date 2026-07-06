#!/usr/bin/env python3
"""
Tether agent registry — the single source of truth for the team.

A small JSON file (default ~/.config/tether/agents.json) maps each agent to the
command that launches its CLI. Everything reads from here:

  - `tether mux --agent codex`  → looks up codex's command, runs it in a PTY
  - the dashboard network graph  → pre-populates known agents
  - process detection            → cross-refs running CLIs against the registry

Duplicates are first-class: two Claude Code instances are just two entries with
distinct ids (claude, claude-2) sharing the same command.

Schema (per entry):
  id       short unique identity used on the wire and the graph (e.g. "codex")
  name     display name (e.g. "Codex")
  cli      human label of the underlying tool (e.g. "Codex CLI")
  command  shell command that launches it (e.g. "codex"). EDIT THESE to match
           your actual binaries — the defaults are best-guess placeholders.
"""
import json
import os
import shlex
from pathlib import Path


DEFAULT_AGENTS = [
    {"id": "claude", "name": "Claude", "cli": "Claude Code", "command": "claude"},
    {"id": "codex", "name": "Codex", "cli": "Codex CLI", "command": "codex"},
    {"id": "gemini", "name": "Gemini", "cli": "Antigravity CLI", "command": "antigravity"},
    {"id": "kilo", "name": "Kilo", "cli": "Kilo Code", "command": "kilo"},
    {"id": "hermes", "name": "Hermes", "cli": "Hermes Agent", "command": "hermes"},
    {"id": "pi", "name": "Pi", "cli": "Pi Agent", "command": "pi"},
]


def config_path() -> str:
    base = os.environ.get("TETHER_CONFIG_HOME")
    if not base:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = xdg if xdg else os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "tether", "agents.json")


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def load_agents() -> list[dict]:
    """Load the registry, seeding the default file on first run."""
    path = config_path()
    if not os.path.exists(path):
        save_agents(DEFAULT_AGENTS)
        return [dict(a) for a in DEFAULT_AGENTS]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        agents = data.get("agents", []) if isinstance(data, dict) else data
        return [a for a in agents if isinstance(a, dict) and a.get("id")]
    except (json.JSONDecodeError, OSError):
        return [dict(a) for a in DEFAULT_AGENTS]


def save_agents(agents: list[dict]) -> None:
    path = config_path()
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"agents": agents}, f, indent=2)
        f.write("\n")


def get_command(agent_id: str) -> list[str] | None:
    """Return the launch command for an agent id, split into argv. None if unknown."""
    for a in load_agents():
        if a.get("id") == agent_id:
            cmd = a.get("command")
            if cmd:
                return shlex.split(cmd)
            return None
    return None


def upsert_agent(entry: dict) -> list[dict]:
    """Add or update an agent by id. Returns the full updated list."""
    agent_id = entry.get("id")
    if not agent_id:
        raise ValueError("agent entry requires an id")
    agents = load_agents()
    for i, a in enumerate(agents):
        if a.get("id") == agent_id:
            agents[i] = {**a, **entry}
            break
    else:
        agents.append({
            "id": agent_id,
            "name": entry.get("name", agent_id),
            "cli": entry.get("cli", ""),
            "command": entry.get("command", ""),
        })
    save_agents(agents)
    return agents


def remove_agent(agent_id: str) -> list[dict]:
    agents = [a for a in load_agents() if a.get("id") != agent_id]
    save_agents(agents)
    return agents
