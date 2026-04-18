"""Passphrase-authenticated encrypted peer connections for TetherLite."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Final

from argon2.low_level import Type, hash_secret_raw
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox
from spake2 import SPAKE2_A, SPAKE2_B

from tether.exceptions import E_PAKE_AUTH_FAILED, E_PAKE_PROTOCOL

logger = logging.getLogger(__name__)

DEFAULT_P2P_PORT: Final[int] = 64327
RENDEZVOUS_TTL_SECONDS: Final[float] = 30.0
POLL_INTERVAL_SECONDS: Final[float] = 0.25
_PROTO_MAGIC: Final[bytes] = b"THP1"
_SALT_SIZE: Final[int] = 16
_AUTH_INIT: Final[bytes] = b"tether-pake-init"
_AUTH_ACK: Final[bytes] = b"tether-pake-ack"


class SecureChannel:
    """Encrypted length-prefixed byte stream over a connected socket."""

    def __init__(self, sock: socket.socket, key: bytes) -> None:
        self._sock = sock
        self._box = SecretBox(key)

    def send_bytes(self, payload: bytes) -> None:
        """Encrypt and send a payload frame."""
        encrypted = bytes(self._box.encrypt(payload))
        _send_frame(self._sock, encrypted)

    def recv_bytes(self) -> bytes:
        """Receive and decrypt a payload frame."""
        encrypted = _recv_frame(self._sock)
        try:
            return bytes(self._box.decrypt(encrypted))
        except CryptoError as exc:
            raise E_PAKE_AUTH_FAILED("encrypted payload could not be decrypted") from exc

    def close(self) -> None:
        """Close the underlying socket."""
        self._sock.close()

    def __enter__(self) -> "SecureChannel":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class PakeListener:
    """Single-listener helper for SPAKE2-authenticated inbound connections."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = DEFAULT_P2P_PORT,
        timeout: float = 10.0,
    ) -> None:
        self._server = socket.create_server((host, port), backlog=1)
        self._server.settimeout(timeout)
        self.timeout = timeout
        self.host, self.port = _sock_host_port(self._server)

    def accept(self, passphrase: str) -> tuple[SecureChannel, tuple[str, int]]:
        """Accept a single inbound connection and authenticate it."""
        conn, addr = self._server.accept()
        conn.settimeout(self.timeout)
        try:
            channel = _server_handshake(conn, passphrase)
        except Exception:
            conn.close()
            raise
        return channel, addr

    def close(self) -> None:
        """Close the listening socket."""
        self._server.close()

    def __enter__(self) -> "PakeListener":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def connect_secure_channel(
    passphrase: str,
    host: str = "127.0.0.1",
    port: int = DEFAULT_P2P_PORT,
    timeout: float = 10.0,
) -> SecureChannel:
    """Connect to a peer and establish a passphrase-authenticated secure channel."""
    conn = socket.create_connection((host, port), timeout=timeout)
    conn.settimeout(timeout)
    try:
        return _client_handshake(conn, passphrase)
    except Exception:
        conn.close()
        raise


def connect_secure_channel_wan(
    passphrase: str,
    relay_url: str,
    api_key: str,
    local_addr: str,
    timeout: float = RENDEZVOUS_TTL_SECONDS,
) -> tuple[str, SecureChannel]:
    """Create a rendezvous session, wait for a peer, and connect as initiator."""
    token = _create_rendezvous_session(relay_url, api_key, local_addr)
    peer_addr = _poll_rendezvous_session(relay_url, token, timeout=timeout)
    host, port = _parse_addr(peer_addr)
    channel = connect_secure_channel(passphrase=passphrase, host=host, port=port, timeout=timeout)
    return token, channel


def listen_secure_channel_wan(
    passphrase: str,
    relay_url: str,
    token: str,
    local_addr: str,
    timeout: float = RENDEZVOUS_TTL_SECONDS,
) -> SecureChannel:
    """Join a rendezvous session and wait for the initiator to connect."""
    _join_rendezvous_session(relay_url, token, local_addr)
    host, port = _parse_addr(local_addr)
    listener = PakeListener(host=host, port=port, timeout=timeout)
    try:
        channel, _ = listener.accept(passphrase)
    except Exception:
        listener.close()
        raise
    listener.close()
    return channel


def _client_handshake(sock: socket.socket, passphrase: str) -> SecureChannel:
    """Complete the client side of the PAKE handshake."""
    header = _recv_exact(sock, len(_PROTO_MAGIC) + _SALT_SIZE)
    if not header.startswith(_PROTO_MAGIC):
        raise E_PAKE_PROTOCOL("invalid PAKE greeting")
    salt = header[len(_PROTO_MAGIC) :]
    password = _derive_password(passphrase, salt)
    initiator = SPAKE2_A(password, idA=b"tether-connect", idB=b"tether-listen")
    outbound = initiator.start()
    _send_frame(sock, outbound)
    inbound = _recv_frame(sock)
    key = _session_key(initiator.finish(inbound), salt)
    channel = SecureChannel(sock, key)
    channel.send_bytes(_AUTH_INIT)
    try:
        ack = channel.recv_bytes()
    except E_PAKE_PROTOCOL as exc:
        raise E_PAKE_AUTH_FAILED("peer failed PAKE key confirmation") from exc
    if not hmac.compare_digest(ack, _AUTH_ACK):
        raise E_PAKE_AUTH_FAILED("peer failed PAKE key confirmation")
    return channel


def _server_handshake(sock: socket.socket, passphrase: str) -> SecureChannel:
    """Complete the server side of the PAKE handshake."""
    salt = hashlib.blake2b(os.urandom(_SALT_SIZE), digest_size=_SALT_SIZE).digest()
    sock.sendall(_PROTO_MAGIC + salt)
    password = _derive_password(passphrase, salt)
    responder = SPAKE2_B(password, idA=b"tether-connect", idB=b"tether-listen")
    inbound = _recv_frame(sock)
    outbound = responder.start()
    _send_frame(sock, outbound)
    key = _session_key(responder.finish(inbound), salt)
    channel = SecureChannel(sock, key)
    try:
        proof = channel.recv_bytes()
        if not hmac.compare_digest(proof, _AUTH_INIT):
            raise E_PAKE_AUTH_FAILED("peer failed PAKE key confirmation")
        channel.send_bytes(_AUTH_ACK)
    except E_PAKE_AUTH_FAILED:
        raise
    except E_PAKE_PROTOCOL as exc:
        raise E_PAKE_AUTH_FAILED("peer failed PAKE key confirmation") from exc
    return channel


def _derive_password(passphrase: str, salt: bytes) -> bytes:
    """Stretch a passphrase into SPAKE2 input material with Argon2id."""
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )


def _session_key(shared_key: bytes, salt: bytes) -> bytes:
    """Derive the SecretBox session key from SPAKE2 output."""
    return hashlib.blake2b(shared_key + salt + b"tether-lite-pake-v1", digest_size=SecretBox.KEY_SIZE).digest()


def _send_frame(sock: socket.socket, payload: bytes) -> None:
    """Send a length-prefixed frame."""
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def _recv_frame(sock: socket.socket) -> bytes:
    """Receive a length-prefixed frame."""
    raw_size = _recv_exact(sock, 4)
    size = struct.unpack(">I", raw_size)[0]
    if size <= 0:
        raise E_PAKE_PROTOCOL("invalid PAKE frame size")
    return _recv_exact(sock, size)


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    """Read exactly size bytes or raise protocol error."""
    remaining = size
    chunks: list[bytes] = []
    while remaining > 0:
        try:
            chunk = sock.recv(remaining)
        except TimeoutError as exc:
            raise E_PAKE_PROTOCOL("timed out during PAKE exchange") from exc
        if not chunk:
            raise E_PAKE_PROTOCOL("unexpected EOF during PAKE exchange")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _sock_host_port(sock: socket.socket) -> tuple[str, int]:
    """Normalize socket address tuples."""
    addr = sock.getsockname()
    return str(addr[0]), int(addr[1])


def _create_rendezvous_session(relay_url: str, api_key: str, addr: str) -> str:
    """Create a rendezvous session and return its token."""
    status_code, payload = _request_json(
        method="POST",
        url=f"{relay_url.rstrip('/')}/v1/rendezvous/session",
        payload={"addr": addr},
        bearer_token=api_key,
    )
    if status_code != 200 or not isinstance(payload.get("token"), str):
        raise E_PAKE_PROTOCOL(f"failed to create rendezvous session: {status_code}")
    return str(payload["token"])


def _join_rendezvous_session(relay_url: str, token: str, addr: str) -> str:
    """Join a rendezvous session and return the initiator address."""
    status_code, payload = _request_json(
        method="POST",
        url=f"{relay_url.rstrip('/')}/v1/rendezvous/session/{token}",
        payload={"addr": addr},
    )
    if status_code != 200 or not isinstance(payload.get("peer_addr"), str):
        raise E_PAKE_PROTOCOL(f"failed to join rendezvous session: {status_code}")
    return str(payload["peer_addr"])


def _poll_rendezvous_session(relay_url: str, token: str, timeout: float) -> str:
    """Poll until a peer address becomes available."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_code, payload = _request_json(
            method="GET",
            url=f"{relay_url.rstrip('/')}/v1/rendezvous/session/{token}",
        )
        if status_code == 200 and isinstance(payload.get("peer_addr"), str):
            return str(payload["peer_addr"])
        if status_code == 202:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if status_code == 404:
            raise E_PAKE_PROTOCOL("rendezvous session expired or missing")
        raise E_PAKE_PROTOCOL(f"unexpected rendezvous poll status: {status_code}")
    raise E_PAKE_PROTOCOL("timed out waiting for rendezvous peer")


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    bearer_token: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Perform a JSON HTTP request and return status plus parsed payload."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return int(response.status), parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {}
        return int(exc.code), parsed
    except (OSError, ValueError) as exc:
        raise E_PAKE_PROTOCOL(f"rendezvous request failed: {url}") from exc


def _parse_addr(addr: str) -> tuple[str, int]:
    """Parse a host:port address string."""
    host, sep, port = addr.rpartition(":")
    if not sep or not host:
        raise E_PAKE_PROTOCOL(f"invalid address: {addr}")
    try:
        return host, int(port)
    except ValueError as exc:
        raise E_PAKE_PROTOCOL(f"invalid address: {addr}") from exc
