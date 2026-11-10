from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_client, ensure_indexes
from app.routers import debug, derived_patterns, patterns, shoes, ws

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast and loudly if SIDE_BET_WINDOW isn't one of the N values the
    # seeded corpus actually supports — never silently fall back to a
    # different N / stats (see docs/side-bet-lucky6-plan.md §1).
    settings.validate_side_bet_window()
    logger.info(
        "Side Bet: window=%s dataset=%s supported=%s",
        settings.side_bet_window,
        settings.side_bet_dataset,
        settings.side_bet_supported_window_list,
    )

    logger.info("Starting up: ensuring Mongo indexes...")
    try:
        await ensure_indexes()
    except Exception:
        logger.exception("Failed to ensure indexes (continuing anyway for local dev)")
    yield
    await close_client()


app = FastAPI(title="Baccarat Vector Match Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shoes.router)
app.include_router(patterns.router)
app.include_router(derived_patterns.router)
app.include_router(debug.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
