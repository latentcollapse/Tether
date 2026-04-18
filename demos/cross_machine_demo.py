#!/usr/bin/env python3
"""Cross-machine relay demo using relay-stored encrypted envelopes."""

from __future__ import annotations

import argparse
import json
import sys

from tether.crypto import ENCRYPTED_ENVELOPE_CONTENT_TYPE, build_encrypted_envelope, generate_keypair, resolve_encrypted_bytes
from tether.relay_client import RelayAgent, run


def run_senior(relay_url: str, name: str) -> int:
    pubkey, privkey = generate_keypair()
    agent = RelayAgent.register(relay_url, name, description="Senior demo agent", pubkey=pubkey)
    sys.stdout.write(json.dumps({"agent_id": agent.agent_id, "api_key": agent.api_key, "pubkey": pubkey}) + "\n")
    sys.stdout.flush()

    incoming = run(agent.wait_for_handle())
    payload = json.loads(resolve_encrypted_bytes(agent.fetch_blob(str(incoming["handle"])), privkey))
    sys.stdout.write(f"received from {incoming['from']}: {json.dumps(payload)}\n")
    sys.stdout.flush()

    sender_pubkey = agent.get_pubkey(str(incoming["from"]))
    reply = {
        "diagnosis": f"Resolved issue for {payload['task']}",
        "next_action": "apply patch and rerun the failing path",
    }
    handle, data = build_encrypted_envelope(json.dumps(reply), sender_pubkey)
    agent.upload_blob(handle, ENCRYPTED_ENVELOPE_CONTENT_TYPE, data)
    agent.route_handle(handle, str(incoming["from"]), "Senior response", ticket_id="T-052", tags=["demo", "reply"])
    sys.stdout.write(f"replied with {handle}\n")
    return 0


def run_junior(relay_url: str, name: str, target_name: str) -> int:
    pubkey, privkey = generate_keypair()
    agent = RelayAgent.register(relay_url, name, description="Junior demo agent", pubkey=pubkey)
    target_agent_id = agent.find_agent_id(target_name)
    target_pubkey = agent.get_pubkey(target_agent_id)

    request_payload = {
        "task": "Relay websocket delivery failed after deploy",
        "evidence": ["message queued", "recipient offline earlier", "need guidance"],
    }
    handle, data = build_encrypted_envelope(json.dumps(request_payload), target_pubkey)
    agent.upload_blob(handle, ENCRYPTED_ENVELOPE_CONTENT_TYPE, data)
    routed = agent.route_handle(handle, target_agent_id, "Junior asks Senior", ticket_id="T-052", tags=["demo", "request"])
    sys.stdout.write(f"sent {handle}: {json.dumps(routed)}\n")
    sys.stdout.flush()

    incoming = run(agent.wait_for_handle())
    response = json.loads(resolve_encrypted_bytes(agent.fetch_blob(str(incoming["handle"])), privkey))
    sys.stdout.write(f"reply: {json.dumps(response)}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-machine encrypted relay demo")
    parser.add_argument("--relay-url", required=True)
    parser.add_argument("--role", choices=("junior", "senior"), required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--target-name", help="Required for junior mode")
    args = parser.parse_args(argv)

    if args.role == "senior":
        return run_senior(args.relay_url, args.name)
    if not args.target_name:
        parser.error("--target-name is required for junior mode")
    return run_junior(args.relay_url, args.name, args.target_name)


if __name__ == "__main__":
    raise SystemExit(main())
