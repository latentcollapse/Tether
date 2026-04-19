"""TetherLite TOML-backed runtime."""

from .runtime import MessageNotFound, TetherLiteRuntime

DEFAULT_P2P_PORT = 7800


def __getattr__(name):
    """Lazy import PAKE symbols — only load spake2/argon2 when actually used."""
    _pake_names = {
        "PakeListener", "SecureChannel",
        "connect_secure_channel", "connect_secure_channel_wan",
        "listen_secure_channel_wan",
    }
    if name in _pake_names:
        from . import pake as _pake
        return getattr(_pake, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_P2P_PORT",
    "MessageNotFound",
    "PakeListener",
    "SecureChannel",
    "TetherLiteRuntime",
    "connect_secure_channel",
    "connect_secure_channel_wan",
    "listen_secure_channel_wan",
]
