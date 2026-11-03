"""Core matching engine: turns the current round window into an embedding
and runs $vectorSearch against the patterns collection."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import PATTERN_VECTOR_INDEX, get_db
from app.models.schemas import MatchResult, PatternMatch
from app.services.embedder import embed_text
from app.services.window_text import describe_window_in_nl

logger = logging.getLogger(__name__)


async def get_recent_window(shoe_id: str) -> list[str]:
    """Fetch the most recent MAX_WINDOW rounds for a shoe, oldest-first."""
    settings = get_settings()
    db = get_db()
    cursor = (
        db.rounds.find({"shoeId": shoe_id})
        .sort("roundNo", -1)
        .limit(settings.max_window)
    )
    rounds = await cursor.to_list(length=settings.max_window)
    rounds.reverse()
    return [r["result"] for r in rounds]


async def vector_search_patterns(query_vector: list[float], top_k: int) -> list[dict]:
    db = get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": PATTERN_VECTOR_INDEX,
                "path": "vector",
                "queryVector": query_vector,
                "numCandidates": max(50, top_k * 10),
                "limit": top_k,
                "filter": {"enabled": True},
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "predictedNext": 1,
                "baseConfidence": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.patterns.aggregate(pipeline)
    return await cursor.to_list(length=top_k)


async def match_window(shoe_id: str, round_no: int) -> MatchResult | None:
    """Full pipeline: fetch window -> describe_window_in_nl -> embed(query)
    -> $vectorSearch -> threshold -> MatchResult. Returns None if the shoe
    does not yet have enough rounds for a meaningful window."""
    settings = get_settings()
    window = await get_recent_window(shoe_id)

    if len(window) < settings.min_window_for_match:
        return None

    text = describe_window_in_nl(window)
    query_vector = await embed_text(text, mode="query")
    raw_hits = await vector_search_patterns(query_vector, settings.top_k)

    top_matches: list[PatternMatch] = []
    for hit in raw_hits:
        score = hit["score"]
        low_confidence = score < settings.pattern_min_score
        top_matches.append(
            PatternMatch(
                patternId=str(hit["_id"]),
                name=hit["name"],
                score=round(score, 4),
                predictedNext=hit["predictedNext"],
                confidence=hit["baseConfidence"],
                lowConfidence=low_confidence,
            )
        )

    no_match = len(top_matches) == 0

    # Demo UX decision: even below threshold, surface top1 but flagged
    # lowConfidence=True so the frontend can show "低信心" badge instead of
    # hiding results entirely.
    if not no_match and all(m.lowConfidence for m in top_matches):
        top_matches = top_matches[:1]

    result = MatchResult(
        shoeId=shoe_id,
        roundNo=round_no,
        currentWindow="".join(window),
        currentWindowText=text,
        topMatches=top_matches,
        noMatch=no_match,
    )

    db = get_db()
    doc = result.model_dump()
    await db.matches.insert_one(doc)

    return result
