"""FastAPI application for the Tether relay."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from . import auth
from .config import get_config
from .db import RelayDB
from .routers import agents, handles, keys, ws

logger = logging.getLogger(__name__)


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
app.include_router(agents.router)
app.include_router(handles.router)
app.include_router(keys.router)
app.include_router(ws.router)
