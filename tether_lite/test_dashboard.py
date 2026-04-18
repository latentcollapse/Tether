from pathlib import Path

from tether_lite import __main__ as tether_lite_main


class _FakeSocket:
    def __init__(self, occupied_ports: set[int]) -> None:
        self.occupied_ports = occupied_ports

    def __enter__(self) -> "_FakeSocket":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def connect_ex(self, address: tuple[str, int]) -> int:
        return 0 if address[1] in self.occupied_ports else 1


def test_find_open_port_skips_bound_port(monkeypatch) -> None:
    monkeypatch.setattr(
        tether_lite_main.socket,
        "socket",
        lambda: _FakeSocket({3000}),
    )

    port = tether_lite_main.find_open_port(3000)

    assert port != 3000
    assert port > 3000


def test_launch_dashboard_reports_missing_dist(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setenv("TETHER_DASHBOARD_DIST", str(tmp_path / "missing-dist"))

    exit_code = tether_lite_main.launch_dashboard()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == "Run `npm run build` in tether-dashboard/ first\n"
