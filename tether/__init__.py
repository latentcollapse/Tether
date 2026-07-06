"""Tether Runtime - Python implementation of the Tether data transfer format."""

__version__ = "3.0.0"

# NOTE (3.0.0): the legacy `TetherRuntime` (full_runtime.py) was retired — superseded by
# SQLiteRuntime, no internal consumers. Moved to the (gitignored) archive/. This drops a
# public symbol, hence the major version bump. Use SQLiteRuntime.
from .runtime import Runtime
from .sqlite_runtime import SQLiteRuntime
from .lc import encode_lc_b, decode_lc_b
from .transport import Transport, create_transport
from .exceptions import (
    TetherError,
    E_LC_PARSE,
    E_LC_BINARY_DECODE,
    E_HANDLE_INVALID,
    E_HANDLE_UNRESOLVED,
    E_FIELD_ORDER,
    E_CONTRACT_STRUCTURE,
    E_TRANSPORT_ERROR
)

__all__ = [
    "Runtime",
    "SQLiteRuntime",
    "Transport",
    "create_transport",
    "encode_lc_b",
    "decode_lc_b",
    "TetherError",
    "E_LC_PARSE",
    "E_LC_BINARY_DECODE",
    "E_HANDLE_INVALID",
    "E_HANDLE_UNRESOLVED",
    "E_FIELD_ORDER",
    "E_CONTRACT_STRUCTURE",
    "E_TRANSPORT_ERROR",
]
