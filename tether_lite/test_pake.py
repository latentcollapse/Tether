import threading
import time

import pytest

from tether.exceptions import E_PAKE_AUTH_FAILED
from tether_lite.pake import _client_handshake, _server_handshake


def test_pake_lan_round_trip() -> None:
    client_sock, server_sock = _socket_pair()
    received: list[bytes] = []
    errors: list[Exception] = []

    def server() -> None:
        try:
            with _server_handshake(server_sock, "shared-secret") as channel:
                received.append(channel.recv_bytes())
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    thread = threading.Thread(target=server)
    thread.start()
    try:
        with _client_handshake(client_sock, "shared-secret") as channel:
            channel.send_bytes(b"h&l_messages_abc123")
    finally:
        thread.join(timeout=5.0)

    assert errors == []
    assert received == [b"h&l_messages_abc123"]


def test_wrong_passphrase_is_rejected() -> None:
    client_sock, server_sock = _socket_pair()
    errors: list[Exception] = []

    def server() -> None:
        try:
            with _server_handshake(server_sock, "shared-secret") as channel:
                channel.recv_bytes()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=server)
    thread.start()
    try:
        with pytest.raises(E_PAKE_AUTH_FAILED):
            with _client_handshake(client_sock, "wrong-secret"):
                pass
    finally:
        thread.join(timeout=5.0)

    assert any(isinstance(exc, E_PAKE_AUTH_FAILED) for exc in errors)


def test_proxy_cannot_read_passphrase_or_payload() -> None:
    client_sock, proxy_client = _socket_pair()
    proxy_server, server_sock = _socket_pair()
    transcript = bytearray()
    received: list[bytes] = []

    proxy = _RecordingProxy(proxy_client, proxy_server, transcript)

    def server() -> None:
        with _server_handshake(server_sock, "shadow-lan") as channel:
            received.append(channel.recv_bytes())

    server_thread = threading.Thread(target=server)
    server_thread.start()
    proxy.start()
    try:
        with _client_handshake(client_sock, "shadow-lan") as channel:
            channel.send_bytes(b"top-secret-handle")
    finally:
        server_thread.join(timeout=5.0)
        proxy.join(timeout=5.0)

    raw = bytes(transcript)
    assert b"shadow-lan" not in raw
    assert b"top-secret-handle" not in raw
    assert received == [b"top-secret-handle"]


class _RecordingProxy(threading.Thread):
    def __init__(self, inbound: "_MemorySocket", outbound: "_MemorySocket", transcript: bytearray) -> None:
        super().__init__(daemon=True)
        self._inbound = inbound
        self._outbound = outbound
        self._transcript = transcript

    def run(self) -> None:
        threads = [
            threading.Thread(target=self._pipe, args=(self._inbound, self._outbound), daemon=True),
            threading.Thread(target=self._pipe, args=(self._outbound, self._inbound), daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)
        self._inbound.close()
        self._outbound.close()

    def _pipe(self, source: "_MemorySocket", target: "_MemorySocket") -> None:
        while True:
            chunk = source.recv(4096)
            if not chunk:
                target.close()
                break
            self._transcript.extend(chunk)
            target.sendall(chunk)


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
