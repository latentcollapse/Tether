"""Tether Runtime - Python implementation of the Tether data transfer format."""

__version__ = "1.0.0"

from .full_runtime import TetherRuntime
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
    "TetherRuntime",
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
