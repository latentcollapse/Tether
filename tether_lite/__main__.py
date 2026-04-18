"""CLI entrypoints for TetherLite."""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
from functools import partial
from pathlib import Path


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
    candidates: list[Path] = []
    if env_dist:
        candidates.append(Path(env_dist))

    repo_root = Path(__file__).resolve().parent.parent
    candidates.extend(
        [
            repo_root / "tether-dashboard" / "dist",
            repo_root.parent / "Tether" / "tether-dashboard" / "dist",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def launch_dashboard() -> int:
    """Serve the built dashboard locally and open it in a browser."""
    dist_dir = find_dashboard_dist()
    if dist_dir is None:
        sys.stdout.write("Run `npm run build` in tether-dashboard/ first\n")
        return 1

    port = find_open_port()
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(dist_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}"
    _open_browser(url)
    sys.stdout.write(f"Tether dashboard running at {url}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch the TetherLite CLI."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stdout.write("Usage: python -m tether_lite dashboard\n")
        return 0
    if args[0] == "dashboard":
        return launch_dashboard()
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


if __name__ == "__main__":
    raise SystemExit(main())
