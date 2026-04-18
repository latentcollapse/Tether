"""FastAPI application for the Tether relay."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth
from .config import get_config
from .db import RelayDB
from .routers import admin, agents, billing, handles, keys, rendezvous, ws

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIST = REPO_ROOT / "tether-dashboard" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and close relay resources."""
    config = get_config()
    db = RelayDB(config.db_path)
    auth.set_db(db)
    app.state.db = db
    logger.info("relay started", extra={"db_path": config.db_path})
    try:
        yield
    finally:
        auth.set_db(None)
        db.close()
        logger.info("relay stopped")


app = FastAPI(title="Tether Relay", version="0.1.0", lifespan=lifespan)
app.include_router(admin.router)
app.include_router(agents.router)
app.include_router(billing.router)
app.include_router(handles.router)
app.include_router(keys.router)
app.include_router(rendezvous.router)
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict[str, object]:
    config = get_config()
    db: RelayDB | None = getattr(app.state, "db", None)
    return {
        "status": "ok",
        "mode": "relay",
        "version": app.version,
        "dashboard": DASHBOARD_DIST.is_dir(),
        "agents": db.count_agents() if db is not None else 0,
        "db_path": config.db_path,
    }


if DASHBOARD_DIST.is_dir():
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIST, html=True), name="dashboard")

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")
