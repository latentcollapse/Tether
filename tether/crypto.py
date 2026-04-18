"""Encrypted Tether envelope helpers."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from nacl.exceptions import CryptoError
from nacl.public import Box, PrivateKey, PublicKey
from nacl.utils import random

from tether.handles import BLOB_PREFIX, canonical_json, digest12, kvfold_dir, suffix

ENCRYPTED_ENVELOPE_CONTENT_TYPE = "application/vnd.tether.encrypted-envelope+json"


def generate_keypair() -> tuple[str, str]:
    """Generate an X25519 keypair encoded as base64 strings."""
    private_key = PrivateKey.generate()
    public_key = private_key.public_key
    return _b64encode(bytes(public_key)), _b64encode(bytes(private_key))


def collapse_encrypted(payload: str, recipient_pubkey_b64: str) -> str:
    """Encrypt a plaintext payload for a recipient and store a blob handle."""
    handle, data = build_encrypted_envelope(payload, recipient_pubkey_b64)
    root = _kvfold_root()
    digest = suffix(handle, BLOB_PREFIX)
    (root / digest).write_bytes(data)
    (root / f"{digest}.toml").write_text(
        f"handle = {json.dumps(handle)}\ncontent_type = {json.dumps(ENCRYPTED_ENVELOPE_CONTENT_TYPE)}\n",
        encoding="utf-8",
    )
    return handle


def resolve_encrypted(handle: str, privkey_b64: str) -> str:
    """Decrypt an encrypted blob handle using the recipient private key."""
    raw = (_kvfold_root() / suffix(handle, BLOB_PREFIX)).read_bytes()
    return resolve_encrypted_bytes(raw, privkey_b64)


def build_encrypted_envelope(payload: str, recipient_pubkey_b64: str) -> tuple[str, bytes]:
    """Return the encrypted-envelope handle and canonical envelope bytes."""
    recipient_key = PublicKey(_b64decode(recipient_pubkey_b64, "recipient public key"))
    ephemeral_private = PrivateKey.generate()
    box = Box(ephemeral_private, recipient_key)
    nonce = random(Box.NONCE_SIZE)
    encrypted = box.encrypt(payload.encode("utf-8"), nonce)
    envelope = {
        "encrypted_payload": _b64encode(bytes(encrypted.ciphertext)),
        "ephemeral_pubkey": _b64encode(bytes(ephemeral_private.public_key)),
        "nonce": _b64encode(nonce),
    }
    data = canonical_json(envelope)
    return f"{BLOB_PREFIX}{digest12(data)}", data


def resolve_encrypted_bytes(raw: bytes, privkey_b64: str) -> str:
    """Decrypt canonical encrypted-envelope bytes using the recipient private key."""
    envelope = json.loads(raw.decode("utf-8"))
    if not isinstance(envelope, dict):
        raise ValueError("encrypted envelope has invalid shape")
    required_keys = {"encrypted_payload", "ephemeral_pubkey", "nonce"}
    if required_keys - set(envelope):
        raise ValueError("encrypted envelope is missing fields")

    private_key = PrivateKey(_b64decode(privkey_b64, "recipient private key"))
    ephemeral_public = PublicKey(_b64decode(str(envelope["ephemeral_pubkey"]), "ephemeral public key"))
    nonce = _b64decode(str(envelope["nonce"]), "nonce")
    encrypted_payload = _b64decode(str(envelope["encrypted_payload"]), "encrypted payload")
    box = Box(private_key, ephemeral_public)
    try:
        plaintext = box.decrypt(encrypted_payload, nonce)
    except CryptoError as exc:
        raise ValueError("failed to decrypt encrypted envelope") from exc
    return plaintext.decode("utf-8")


def _kvfold_root() -> Path:
    """Return the KVFold root used for encrypted blobs."""
    return kvfold_dir(Path("kvfold"))


def _b64encode(data: bytes) -> str:
    """Encode bytes as ASCII base64."""
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str, label: str) -> bytes:
    """Decode base64 input with a stable error surface."""
    try:
        return base64.b64decode(data.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"invalid {label} base64") from exc
