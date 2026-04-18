"""Minimal relay client for encrypted cross-machine demos."""

from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

import websockets


def _json_request(url: str, method: str, payload: dict[str, Any] | None = None, api_key: str | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key is not None:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
    return json.loads(raw.decode("utf-8"))


@dataclass(frozen=True)
class RelayAgent:
    relay_url: str
    agent_id: str
    api_key: str
    name: str

    @classmethod
    def register(cls, relay_url: str, name: str, description: str | None = None, pubkey: str | None = None) -> "RelayAgent":
        payload: dict[str, Any] = {"name": name}
        if description is not None:
            payload["description"] = description
        if pubkey is not None:
            payload["pubkey"] = pubkey
        data = _json_request(f"{relay_url.rstrip('/')}/v1/agents/register", "POST", payload)
        return cls(relay_url=relay_url.rstrip("/"), agent_id=str(data["agent_id"]), api_key=str(data["api_key"]), name=name)

    def list_agents(self) -> list[dict[str, Any]]:
        data = _json_request(f"{self.relay_url}/v1/agents", "GET", api_key=self.api_key)
        if not isinstance(data, list):
            raise RuntimeError("unexpected list_agents response")
        return data

    def find_agent_id(self, name: str) -> str:
        for row in self.list_agents():
            if str(row.get("name")) == name:
                return str(row["agent_id"])
        raise RuntimeError(f"agent not found: {name}")

    def get_pubkey(self, agent_id: str) -> str:
        data = _json_request(f"{self.relay_url}/v1/agents/{agent_id}/pubkey", "GET", api_key=self.api_key)
        return str(data["pubkey"])

    def upload_blob(self, handle: str, content_type: str, payload: bytes) -> dict[str, Any]:
        return _json_request(
            f"{self.relay_url}/v1/handles/blobs",
            "POST",
            {
                "handle": handle,
                "content_type": content_type,
                "payload_b64": base64.b64encode(payload).decode("ascii"),
            },
            api_key=self.api_key,
        )

    def fetch_blob(self, handle: str) -> bytes:
        data = _json_request(f"{self.relay_url}/v1/handles/blobs/{parse.quote(handle, safe='')}", "GET", api_key=self.api_key)
        return base64.b64decode(str(data["payload_b64"]).encode("ascii"), validate=True)

    def route_handle(self, handle: str, to_agent_id: str, subject: str, ticket_id: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"handle": handle, "to": to_agent_id, "subject": subject, "tags": list(tags or [])}
        if ticket_id is not None:
            payload["ticket_id"] = ticket_id
        return _json_request(f"{self.relay_url}/v1/handles/route", "POST", payload, api_key=self.api_key)

    async def wait_for_handle(self) -> dict[str, Any]:
        ws_url = self.relay_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/v1/ws/{self.agent_id}?api_key={parse.quote(self.api_key, safe='')}"
        async with websockets.connect(ws_url, open_timeout=10, ping_interval=20, ping_timeout=20) as websocket:
            await websocket.send(json.dumps({"type": "ping"}))
            pong = json.loads(await websocket.recv())
            if pong.get("type") != "pong":
                raise RuntimeError(f"unexpected websocket handshake response: {pong}")
            while True:
                message = json.loads(await websocket.recv())
                if message.get("type") == "handle":
                    return message


def run(coro: asyncio.Future[Any] | asyncio.coroutines.Coroutine[Any, Any, Any]) -> Any:
    """Run an async helper from sync scripts."""
    return asyncio.run(coro)
