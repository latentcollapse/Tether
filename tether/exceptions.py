"""Tether exceptions."""


class TetherError(Exception):
    """Base exception for Tether errors."""
    pass


class E_LC_PARSE(TetherError):
    """Invalid LC-B syntax."""
    pass


class E_LC_BINARY_DECODE(TetherError):
    """Invalid LC-B encoding."""
    pass


class E_FIELD_ORDER(TetherError):
    """Fields out of order."""
    pass


class E_CANONICALIZATION_FAIL(TetherError):
    """Non-canonical structure (e.g., cycles)."""
    pass


class E_HANDLE_UNRESOLVED(TetherError):
    """Handle requires runtime resolution."""
    pass


class E_HANDLE_INVALID(TetherError):
    """Handle contains non-ASCII or invalid characters."""
    pass


class E_VALIDATION_FAIL(TetherError):
    """Execution requested outside LLM authority."""
    pass


class E_ENV_PAYLOAD_HASH_MISMATCH(TetherError):
    """Merkle root mismatch."""
    pass


class E_ENV_MANIFEST_INVALID(TetherError):
    """Invalid LC_12 manifest."""
    pass


class E_CONTRACT_STRUCTURE(TetherError):
    """Invalid contract object structure."""
    pass


class E_TRANSPORT_ERROR(TetherError):
    """Transport layer error."""
    pass
