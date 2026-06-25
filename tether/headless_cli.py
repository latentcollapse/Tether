"""CLI entrypoints for TetherLite."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from tether.pake import (
    DEFAULT_P2P_PORT,
    PakeListener,
    connect_secure_channel,
    connect_secure_channel_wan,
    listen_secure_channel_wan,
)


def find_open_port(start: int = 3000) -> int:
    """Find an open localhost TCP port starting at the requested port."""
    port = start
    while True:
        with socket.socket() as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
        port += 1


def find_dashboard_dist() -> Path | None:
    """Locate a built Tether dashboard dist directory."""
    env_dist = os.environ.get("TETHER_DASHBOARD_DIST")
    if env_dist:
        candidate = Path(env_dist)
        return candidate if candidate.is_dir() else None

    candidates: list[Path] = []
    repo_root = Path(__file__).resolve().parent.parent
    candidates.extend(
        [
            repo_root / "src" / "dashboard" / "dist",
            repo_root / "tether-dashboard" / "dist",
            repo_root.parent / "Tether" / "src" / "dashboard" / "dist",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def launch_dashboard() -> int:
    """Serve the built dashboard with the full API backend."""
    try:
        from fastapi import FastAPI
        import uvicorn
    except ImportError:
        sys.stderr.write("Error: Dashboard dependencies missing. Please install fastapi and uvicorn:\n")
        sys.stderr.write("  pip install fastapi uvicorn\n")
        return 1

    from tether.__main__ import _create_dashboard_app, _dashboard_db_path, _dashboard_dist_dir

    dist_dir = _dashboard_dist_dir() or find_dashboard_dist()
    if dist_dir is None:
        sys.stdout.write("Run `npm run build` in src/dashboard/ first\n")
        return 1

    host = os.environ.get("TETHER_HOST", "127.0.0.1")
    port_env = os.environ.get("TETHER_PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            sys.stderr.write(f"Invalid TETHER_PORT: {port_env}\n")
            return 1
    else:
        port = find_open_port()

    url = f"http://{host}:{port}"
    app = _create_dashboard_app(dist_dir)
    
    if host in {"127.0.0.1", "localhost"} and os.environ.get("TETHER_HEADLESS") != "1":
        _open_browser(url)
        
    sys.stdout.write(f"Tether dashboard running at {url} — Ctrl+C to stop\n")
    sys.stdout.flush()
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch the TetherLite CLI."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write(
            "Usage: python -m tether_lite dashboard\n"
            "   or: python -m tether_lite connect --passphrase ...\n"
            "   or: python -m tether_lite listen --passphrase ...\n"
        )
        return 0
    if args[0] == "dashboard":
        return launch_dashboard()
    if args[0] == "connect":
        return _run_connect(args[1:])
    if args[0] == "listen":
        return _run_listen(args[1:])
    sys.stderr.write(f"Unknown command: {args[0]}\n")
    return 1


def _open_browser(url: str) -> None:
    """Open the dashboard URL in the platform browser."""
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        if sys.platform == "darwin":
            subprocess.Popen(
                ["open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
    except OSError:
        return


def _run_connect(args: Sequence[str]) -> int:
    """Handle the connect CLI command."""
    parsed = _parse_common_args(args, require_token=False)
    payload = sys.stdin.buffer.read()
    if parsed["wan"]:
        if parsed["relay_url"] is None or parsed["key"] is None or parsed["local_addr"] is None:
            sys.stderr.write("--wan requires --relay-url, --key, and --local-addr\n")
            return 1
        token, channel = connect_secure_channel_wan(
            passphrase=str(parsed["passphrase"]),
            relay_url=str(parsed["relay_url"]),
            api_key=str(parsed["key"]),
            local_addr=str(parsed["local_addr"]),
            timeout=float(parsed["timeout"]),
        )
        sys.stdout.write(f"Rendezvous token: {token}\n")
        with channel:
            channel.send_bytes(payload)
        return 0

    with connect_secure_channel(
        passphrase=str(parsed["passphrase"]),
        host=str(parsed["host"]),
        port=int(parsed["port"]),
        timeout=float(parsed["timeout"]),
    ) as channel:
        channel.send_bytes(payload)
    return 0


def _run_listen(args: Sequence[str]) -> int:
    """Handle the listen CLI command."""
    parsed = _parse_common_args(args, require_token=True)
    if parsed["wan"]:
        if parsed["relay_url"] is None or parsed["local_addr"] is None or parsed["token"] is None:
            sys.stderr.write("--wan requires --relay-url, --token, and --local-addr\n")
            return 1
        with listen_secure_channel_wan(
            passphrase=str(parsed["passphrase"]),
            relay_url=str(parsed["relay_url"]),
            token=str(parsed["token"]),
            local_addr=str(parsed["local_addr"]),
            timeout=float(parsed["timeout"]),
        ) as channel:
            sys.stdout.buffer.write(channel.recv_bytes())
        return 0

    with PakeListener(host=str(parsed["host"]), port=int(parsed["port"]), timeout=float(parsed["timeout"])) as listener:
        with listener.accept(str(parsed["passphrase"]))[0] as channel:
            sys.stdout.buffer.write(channel.recv_bytes())
    return 0


def _parse_common_args(args: Sequence[str], require_token: bool) -> dict[str, object]:
    """Parse shared connect/listen CLI flags."""
    result: dict[str, object] = {
        "passphrase": None,
        "wan": False,
        "relay_url": None,
        "key": None,
        "token": None,
        "local_addr": None,
        "host": "127.0.0.1",
        "port": DEFAULT_P2P_PORT,
        "timeout": 10.0,
    }
    iterator = iter(args)
    for arg in iterator:
        if arg == "--passphrase":
            result["passphrase"] = next(iterator, None)
        elif arg == "--wan":
            result["wan"] = True
        elif arg == "--relay-url":
            result["relay_url"] = next(iterator, None)
        elif arg == "--key":
            result["key"] = next(iterator, None)
        elif arg == "--token":
            result["token"] = next(iterator, None)
        elif arg == "--local-addr":
            result["local_addr"] = next(iterator, None)
        elif arg == "--host":
            result["host"] = next(iterator, None)
        elif arg == "--port":
            raw = next(iterator, None)
            result["port"] = int(raw) if raw is not None else DEFAULT_P2P_PORT
        elif arg == "--timeout":
            raw = next(iterator, None)
            result["timeout"] = float(raw) if raw is not None else 10.0
        else:
            raise SystemExit(f"Unknown argument: {arg}")

    if result["passphrase"] is None:
        raise SystemExit("--passphrase is required")
    if require_token and not result["wan"] and result["token"] is not None:
        raise SystemExit("--token is only valid with --wan")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
