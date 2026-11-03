"""MongoDB Atlas connection and index management (including the Atlas
Vector Search index on the `patterns` collection)."""

from __future__ import annotations

import asyncio
import logging

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

PATTERN_VECTOR_INDEX = "pattern_vec_idx"
DERIVED_PATTERN_VECTOR_INDEX = "derived_pattern_vec_idx"


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri, tlsCAFile=certifi.where())
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        settings = get_settings()
        _db = get_client()[settings.mongo_db_name]
    return _db


async def ensure_indexes() -> None:
    db = get_db()
    settings = get_settings()

    # Standard indexes
    await db.shoes.create_index([("shoeId", ASCENDING)], unique=True)
    await db.shoes.create_index([("status", ASCENDING), ("startedAt", DESCENDING)])
    await db.rounds.create_index([("shoeId", ASCENDING), ("roundNo", ASCENDING)], unique=True)
    await db.patterns.create_index([("name", ASCENDING)], unique=True)
    await db.matches.create_index([("shoeId", ASCENDING), ("roundNo", ASCENDING)])
    await db.matches.create_index([("triggeredAt", DESCENDING)])

    # Derived-road (下三路) pattern library + match history
    await db.derived_patterns.create_index([("name", ASCENDING)], unique=True)
    await db.derived_matches.create_index([("shoeId", ASCENDING), ("roundNo", ASCENDING)])
    await db.derived_matches.create_index([("triggeredAt", DESCENDING)])

    # Atlas Vector Search indexes
    await _ensure_vector_index(
        db, db.patterns, PATTERN_VECTOR_INDEX, settings.voyage_dim
    )
    await _ensure_vector_index(
        db, db.derived_patterns, DERIVED_PATTERN_VECTOR_INDEX, settings.voyage_dim
    )


async def _ensure_vector_index(db: AsyncIOMotorDatabase, collection, index_name: str, dim: int) -> None:
    try:
        existing = await collection.list_search_indexes().to_list(length=None)
        names = {idx.get("name") for idx in existing}
        if index_name in names:
            logger.info("Vector index %s already exists", index_name)
            return
    except OperationFailure as exc:
        logger.warning("Could not list search indexes (may not be Atlas): %s", exc)
        return

    definition = {
        "fields": [
            {
                "type": "vector",
                "path": "vector",
                "numDimensions": dim,
                "similarity": "cosine",
            },
            {"type": "filter", "path": "enabled"},
            {"type": "filter", "path": "category"},
        ]
    }

    try:
        await collection.create_search_index(
            {
                "name": index_name,
                "type": "vectorSearch",
                "definition": definition,
            }
        )
        logger.info("Created vector search index %s, waiting for it to become queryable...", index_name)
        await _wait_for_index_ready(collection, index_name)
    except OperationFailure as exc:
        logger.error("Failed to create vector search index %s: %s", index_name, exc)
        raise


async def _wait_for_index_ready(collection, index_name: str, timeout_s: int = 120) -> None:
    elapsed = 0
    interval = 3
    while elapsed < timeout_s:
        indexes = await collection.list_search_indexes().to_list(length=None)
        for idx in indexes:
            if idx.get("name") == index_name and idx.get("queryable"):
                logger.info("Vector index %s is queryable.", index_name)
                return
        await asyncio.sleep(interval)
        elapsed += interval
    logger.warning("Vector index %s did not become queryable within %ss; continuing anyway.", index_name, timeout_s)


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
