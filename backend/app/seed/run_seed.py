"""One-shot script: ensures indexes exist, then seeds the 10 default
patterns (embedding each via Voyage). Safe to re-run — uses upsert on
pattern name.

Usage:
    python -m app.seed.run_seed
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.db import close_client, ensure_indexes, get_db
from app.seed.default_derived_patterns import DEFAULT_DERIVED_PATTERNS
from app.seed.default_patterns import DEFAULT_PATTERNS
from app.services.derived_roads import DerivedTailSymbols, describe_derived_in_nl
from app.services.embedder import embed_text
from app.services.pattern_service import expand_sequence, infer_structural_category
from app.services.window_text import describe_window_in_nl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_patterns() -> None:
    settings = get_settings()
    db = get_db()

    for p in DEFAULT_PATTERNS:
        seq = expand_sequence(p["canonicalSequence"])
        text = describe_window_in_nl(seq)
        vector = await embed_text(text, mode="document")
        now = datetime.now(timezone.utc)

        doc = {
            "name": p["name"],
            "category": p["category"],
            "nlDescription": p["nlDescription"],
            "canonicalSequence": p["canonicalSequence"],
            "minWindowLen": len(seq),
            "structuralCategory": infer_structural_category(seq),
            "predictedNext": p["predictedNext"],
            "baseConfidence": p["baseConfidence"],
            "textForEmbedding": text,
            "textVersion": settings.nl_describer_version,
            "vector": vector,
            "enabled": True,
            "updatedAt": now,
        }

        existing = await db.patterns.find_one({"name": p["name"]})
        if existing:
            await db.patterns.update_one({"_id": existing["_id"]}, {"$set": doc})
            logger.info("Updated pattern: %s", p["name"])
        else:
            doc["createdAt"] = now
            await db.patterns.insert_one(doc)
            logger.info("Inserted pattern: %s", p["name"])


async def seed_derived_patterns() -> None:
    settings = get_settings()
    db = get_db()

    for p in DEFAULT_DERIVED_PATTERNS:
        roads = DerivedTailSymbols(**p["canonicalRoads"])
        text = describe_derived_in_nl(roads)
        vector = await embed_text(text, mode="document")
        now = datetime.now(timezone.utc)

        doc = {
            "name": p["name"],
            "category": p["category"],
            "nlDescription": p["nlDescription"],
            "canonicalRoads": p["canonicalRoads"],
            "predictedNext": p["predictedNext"],
            "baseConfidence": p["baseConfidence"],
            "textForEmbedding": text,
            "textVersion": settings.nl_derived_describer_version,
            "vector": vector,
            "enabled": True,
            "updatedAt": now,
        }

        existing = await db.derived_patterns.find_one({"name": p["name"]})
        if existing:
            await db.derived_patterns.update_one({"_id": existing["_id"]}, {"$set": doc})
            logger.info("Updated derived pattern: %s", p["name"])
        else:
            doc["createdAt"] = now
            await db.derived_patterns.insert_one(doc)
            logger.info("Inserted derived pattern: %s", p["name"])


async def main() -> None:
    logger.info("Ensuring indexes...")
    await ensure_indexes()
    logger.info("Seeding default patterns...")
    await seed_patterns()
    logger.info("Seeding default derived (下三路) patterns...")
    await seed_derived_patterns()
    logger.info("Done.")
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
