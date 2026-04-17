"""Typed Tether handle helpers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

INLINE_PREFIX = "h&l_inline_"
BLOB_PREFIX = "h&l_blob_"
TREE_PREFIX = "h&l_tree_"
LEGACY_MESSAGES_PREFIX = "h&l_messages_"


def canonical_json(value: Any) -> bytes:
    """Return canonical JSON bytes for hashing and storage."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest12(data: bytes) -> str:
    """Return the 12-character typed-handle digest."""
    try:
        import blake3

        return blake3.blake3(data).hexdigest()[:12]
    except ImportError:
        return hashlib.blake2b(data, digest_size=6).hexdigest()


def handle(prefix: str, data: bytes) -> str:
    """Build a typed handle from a prefix and canonical bytes."""
    return f"{prefix}{digest12(data)}"


def kvfold_dir(default_root: Path | str) -> Path:
    """Return the configured KVFold directory, creating it if needed."""
    root = Path(os.environ.get("TETHER_KVFOLD_DIR", default_root))
    root.mkdir(parents=True, exist_ok=True)
    return root


def suffix(handle_value: str, prefix: str) -> str:
    """Extract a handle suffix after validating its prefix."""
    if not handle_value.startswith(prefix):
        raise ValueError(f"expected handle prefix {prefix!r}: {handle_value}")
    return handle_value[len(prefix) :]
