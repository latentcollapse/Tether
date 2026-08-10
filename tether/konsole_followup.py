"""Retired per-message follow-up entry point.

Kept as a harmless tombstone so stale user services created by older releases
exit without touching a terminal. Delivery is owned by ``delivery_worker``.
"""


def main(argv: list[str] | None = None) -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
