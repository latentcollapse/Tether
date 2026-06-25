import json
import threading
import time
from collections.abc import Iterator

import httpx
import pytest

from relay import auth as relay_auth
from relay.db import RelayDB
from relay.main import app
from relay.routers import rendezvous
from relay.tier import reset_daily_message_counts
from tether.exceptions import E_PAKE_PROTOCOL
from tether import pake


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def relay_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[RelayDB]:
    db_path = tmp_path / "relay.db"
    monkeypatch.setenv("TETHER_RELAY_DB", str(db_path))
    monkeypatch.setenv("TETHER_RELAY_KEY_PREFIX", "tk_test_")
    monkeypatch.setenv("TETHER_RELAY_BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("TETHER_RATE_LIMIT_PER_MIN", "100")
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db = RelayDB(str(db_path))
    relay_auth.set_db(db)
    yield db
    relay_auth.set_db(None)
    relay_auth.reset_rate_limits()
    reset_daily_message_counts()
    db.close()
    rendezvous._sessions.clear()


async def _register(client: httpx.AsyncClient, name: str) -> dict[str, str]:
    response = await client.post("/v1/agents/register", json={"name": name})
    assert response.status_code == 200
    return response.json()


def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


@pytest.mark.anyio
async def test_rendezvous_session_round_trip(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        initiator = await _register(client, "initiator")
        created = await client.post(
            "/v1/rendezvous/session",
            headers=_auth(initiator["api_key"]),
            json={"addr": "1.2.3.4:5678"},
        )
        assert created.status_code == 200
        token = created.json()["token"]

        waiting = await client.get(f"/v1/rendezvous/session/{token}")
        assert waiting.status_code == 202
        assert waiting.json() == {"status": "waiting"}

        joined = await client.post(
            f"/v1/rendezvous/session/{token}",
            json={"addr": "5.6.7.8:9012"},
        )
        assert joined.status_code == 200
        assert joined.json() == {"peer_addr": "1.2.3.4:5678"}

        polled = await client.get(f"/v1/rendezvous/session/{token}")
        assert polled.status_code == 200
        assert polled.json() == {"peer_addr": "5.6.7.8:9012"}


@pytest.mark.anyio
async def test_expired_token_returns_404(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        initiator = await _register(client, "initiator")
        created = await client.post(
            "/v1/rendezvous/session",
            headers=_auth(initiator["api_key"]),
            json={"addr": "1.2.3.4:5678"},
        )
        token = created.json()["token"]
        rendezvous._sessions[token].expires_at = time.monotonic() - 1

        response = await client.get(f"/v1/rendezvous/session/{token}")

        assert response.status_code == 404


@pytest.mark.anyio
async def test_free_tier_is_rejected(relay_env: RelayDB) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        initiator = await _register(client, "initiator")
        relay_env.set_agent_tier(initiator["agent_id"], "free")

        response = await client.post(
            "/v1/rendezvous/session",
            headers=_auth(initiator["api_key"]),
            json={"addr": "1.2.3.4:5678"},
        )

        assert response.status_code == 403
        assert response.json() == {
            "error": "upgrade_required",
            "tier": "free",
            "feature": "pake_wan",
            "upgrade": "upgrade tier for pake_wan",
        }


def test_full_wan_pake_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _FakeRelayBackend()
    transcript = backend.transcript
    registry = _ListenerRegistry()

    monkeypatch.setattr(pake, "_create_rendezvous_session", backend.create)
    monkeypatch.setattr(pake, "_join_rendezvous_session", backend.join)
    monkeypatch.setattr(pake, "_poll_rendezvous_session", backend.poll)
    monkeypatch.setattr(pake, "PakeListener", registry.listener_factory)
    monkeypatch.setattr(pake, "connect_secure_channel", registry.connect)

    holder: dict[str, object] = {}

    def initiator() -> None:
        token, channel = pake.connect_secure_channel_wan(
            passphrase="shadow-lan",
            relay_url="mock://relay",
            api_key="tk_test_initiator",
            local_addr="127.0.0.1:5000",
        )
        holder["token"] = token
        with channel:
            channel.send_bytes(b"top-secret-handle")

    initiator_thread = threading.Thread(target=initiator)
    initiator_thread.start()
    while backend.last_token is None:
        time.sleep(0.01)

    with pake.listen_secure_channel_wan(
        passphrase="shadow-lan",
        relay_url="mock://relay",
        token=backend.last_token,
        local_addr="127.0.0.1:5001",
    ) as channel:
        payload = channel.recv_bytes()

    initiator_thread.join(timeout=5.0)

    raw = json.dumps(transcript)
    assert "shadow-lan" not in raw
    assert "top-secret-handle" not in raw
    assert payload == b"top-secret-handle"
    assert holder["token"] == backend.last_token


def test_missing_token_raises_protocol_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pake, "_join_rendezvous_session", lambda relay_url, token, addr: (_ for _ in ()).throw(E_PAKE_PROTOCOL("missing")))

    with pytest.raises(E_PAKE_PROTOCOL):
        pake.listen_secure_channel_wan(
            passphrase="secret",
            relay_url="mock://relay",
            token="missing",
            local_addr="127.0.0.1:5001",
            timeout=0.1,
        )


class _FakeRelayBackend:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, str | None]] = {}
        self.transcript: list[dict[str, str]] = []
        self.last_token: str | None = None

    def create(self, relay_url: str, api_key: str, addr: str) -> str:
        token = f"token-{len(self.sessions) + 1}"
        self.last_token = token
        self.sessions[token] = {"initiator_addr": addr, "peer_addr": None}
        self.transcript.append({"action": "create", "relay_url": relay_url, "api_key": api_key, "addr": addr})
        return token

    def join(self, relay_url: str, token: str, addr: str) -> str:
        session = self.sessions[token]
        session["peer_addr"] = addr
        self.transcript.append({"action": "join", "relay_url": relay_url, "token": token, "addr": addr})
        return str(session["initiator_addr"])

    def poll(self, relay_url: str, token: str, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            peer_addr = self.sessions[token]["peer_addr"]
            if isinstance(peer_addr, str):
                self.transcript.append({"action": "poll", "relay_url": relay_url, "token": token})
                return peer_addr
            time.sleep(0.01)
        raise E_PAKE_PROTOCOL("timed out waiting for rendezvous peer")


class _ListenerRegistry:
    def __init__(self) -> None:
        self.listeners: dict[tuple[str, int], _MemoryListener] = {}

    def listener_factory(self, host: str = "0.0.0.0", port: int = 0, timeout: float = 10.0) -> "_MemoryListener":
        listener = _MemoryListener(host=host, port=port, timeout=timeout)
        self.listeners[(listener.host, listener.port)] = listener
        return listener

    def connect(self, passphrase: str, host: str, port: int, timeout: float = 10.0) -> pake.SecureChannel:
        listener = self.listeners[(host, port)]
        client_sock, server_sock = _socket_pair()
        listener.enqueue(server_sock)
        return pake._client_handshake(client_sock, passphrase)


class _MemoryListener:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._queue: list[_MemorySocket] = []
        self._condition = threading.Condition()

    def enqueue(self, sock: "_MemorySocket") -> None:
        with self._condition:
            self._queue.append(sock)
            self._condition.notify_all()

    def accept(self, passphrase: str) -> tuple[pake.SecureChannel, tuple[str, int]]:
        with self._condition:
            deadline = time.monotonic() + self.timeout
            while not self._queue:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise E_PAKE_PROTOCOL("timed out waiting for inbound peer")
                self._condition.wait(timeout=remaining)
            sock = self._queue.pop(0)
        channel = pake._server_handshake(sock, passphrase)
        return channel, (self.host, self.port)

    def close(self) -> None:
        return


class _MemorySocket:
    def __init__(self) -> None:
        self._buffer = bytearray()
        self._condition = threading.Condition()
        self._peer: "_MemorySocket | None" = None
        self._closed = False
        self._remote_closed = False
        self._timeout: float | None = None

    def settimeout(self, timeout: float | None) -> None:
        self._timeout = timeout

    def getsockname(self) -> tuple[str, int]:
        return ("127.0.0.1", 0)

    def connect_peer(self, peer: "_MemorySocket") -> None:
        self._peer = peer

    def sendall(self, data: bytes) -> None:
        if self._peer is None:
            raise OSError("socket has no peer")
        with self._peer._condition:
            if self._peer._closed:
                raise OSError("peer is closed")
            self._peer._buffer.extend(data)
            self._peer._condition.notify_all()

    def recv(self, size: int) -> bytes:
        with self._condition:
            deadline = None if self._timeout is None else time.monotonic() + self._timeout
            while not self._buffer and not self._remote_closed:
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("timed out")
                self._condition.wait(timeout=remaining)
            if not self._buffer:
                return b""
            chunk = bytes(self._buffer[:size])
            del self._buffer[:size]
            return chunk

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        if self._peer is not None:
            with self._peer._condition:
                self._peer._remote_closed = True
                self._peer._condition.notify_all()


def _socket_pair() -> tuple[_MemorySocket, _MemorySocket]:
    first = _MemorySocket()
    second = _MemorySocket()
    first.connect_peer(second)
    second.connect_peer(first)
    first.settimeout(5.0)
    second.settimeout(5.0)
    return first, second
