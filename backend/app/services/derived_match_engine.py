"""Second matching engine: turns the current shoe's three derived roads
(下三路: Big Eye Boy / Small Road / Cockroach Pig) into an embedding and runs
$vectorSearch against the derived_patterns collection. Parallels
match_engine.py but on a completely separate collection + vector index so
the two semantic spaces (big-road window text vs. derived-road tail
symbols) never mix."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import DERIVED_PATTERN_VECTOR_INDEX, get_db
from app.models.schemas import DerivedMatchResult, DerivedPatternMatch, DerivedTailSymbolsSchema
from app.services.derived_roads import compute_all_roads, describe_derived_in_nl, extract_tail_symbols
from app.services.embedder import embed_text

logger = logging.getLogger(__name__)


async def get_rounds_sequence(shoe_id: str) -> list[str]:
    """Fetch the entire round sequence for a shoe (oldest-first) — derived
    roads need the full history, not just a fixed-size window, because
    column comparisons can reach arbitrarily far back."""
    db = get_db()
    cursor = db.rounds.find({"shoeId": shoe_id}).sort("roundNo", 1)
    rounds = await cursor.to_list(length=None)
    return [r["result"] for r in rounds]


async def vector_search_derived(query_vector: list[float], top_k: int) -> list[dict]:
    db = get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": DERIVED_PATTERN_VECTOR_INDEX,
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
    cursor = db.derived_patterns.aggregate(pipeline)
    return await cursor.to_list(length=top_k)


async def match_derived(shoe_id: str, round_no: int) -> DerivedMatchResult | None:
    """Full pipeline: fetch full round history -> compute three derived
    roads -> extract tail symbols -> describe_derived_in_nl -> embed(query)
    -> $vectorSearch -> threshold -> DerivedMatchResult.

    Returns None if there aren't enough Big Road columns yet for any
    derived road to have produced a symbol (Cockroach Pig needs the most
    history, so that's the practical gate).
    """
    settings = get_settings()
    results = await get_rounds_sequence(shoe_id)
    if not results:
        return None

    roads = compute_all_roads(results)
    tail = extract_tail_symbols(roads, k=settings.derived_tail_length)

    if not (tail.bigEye or tail.small or tail.cockroach):
        return None

    text = describe_derived_in_nl(tail)
    query_vector = await embed_text(text, mode="query")
    raw_hits = await vector_search_derived(query_vector, settings.derived_top_k)

    threshold = settings.derived_pattern_min_score

    top_matches: list[DerivedPatternMatch] = []
    for hit in raw_hits:
        score = hit["score"]
        # While not yet calibrated (threshold is None), flag everything
        # lowConfidence so the frontend can show a "待校準" style badge
        # instead of implying a trustworthy signal.
        low_confidence = True if threshold is None else score < threshold
        top_matches.append(
            DerivedPatternMatch(
                patternId=str(hit["_id"]),
                name=hit["name"],
                score=round(score, 4),
                predictedNext=hit["predictedNext"],
                confidence=hit["baseConfidence"],
                lowConfidence=low_confidence,
            )
        )

    no_match = len(top_matches) == 0

    if not no_match and all(m.lowConfidence for m in top_matches) and threshold is not None:
        top_matches = top_matches[:1]

    result = DerivedMatchResult(
        shoeId=shoe_id,
        roundNo=round_no,
        currentRoads=DerivedTailSymbolsSchema(bigEye=tail.bigEye, small=tail.small, cockroach=tail.cockroach),
        currentRoadsText=text,
        topMatches=top_matches,
        noMatch=no_match,
    )

    db = get_db()
    doc = result.model_dump()
    await db.derived_matches.insert_one(doc)

    return result
