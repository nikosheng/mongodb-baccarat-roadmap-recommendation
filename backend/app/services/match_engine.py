"""Core matching engine: turns the current round window into an embedding
and runs $vectorSearch against the patterns collection."""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import PATTERN_VECTOR_INDEX, get_db
from app.models.schemas import MatchResult, PatternMatch
from app.services.embedder import embed_text
from app.services.pattern_structure import compatible_categories
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


async def vector_search_patterns(
    query_vector: list[float], top_k: int, window: list[str]
) -> list[dict]:
    """$vectorSearch against the patterns collection, then apply a
    deterministic (non-embedding) structural guard: a pattern is only
    eligible if its `structuralCategory` (a coarse narrative shape derived
    from its canonicalSequence's run decomposition - see
    pattern_structure.py) is still a plausible, not-yet-falsified
    classification of the live window's own run history so far.

    This replaced an earlier raw-length (`minWindowLen`) cutoff, which was
    too blunt: it correctly rejected windows that hadn't had enough rounds
    for *any* version of a narrative to occur, but it also rejected windows
    that were genuinely mid-way through re-enacting a multi-phase narrative
    (e.g. a 7-round window in the middle of "long Banker run, brief Player
    interruption, Banker resumes" just because the full pattern needed 9
    rounds). The categorical check instead asks "has anything happened yet
    that rules this narrative *shape* out?" rather than "has enough time
    passed?" - which also lets business users define custom patterns
    without needing to match exact run lengths (e.g. a window showing
    [B x3, P x2, B x2-in-progress] is recognized as the same "break then
    resume" family as a pattern requiring exactly [B x4, P x1, B x4],
    instead of being excluded on a technicality).

    We over-fetch from $vectorSearch (more than top_k) because this
    post-filter may remove some of the raw hits, and we still want to
    backfill up to top_k eligible candidates.
    """
    db = get_db()
    fetch_limit = max(50, top_k * 10)
    pipeline = [
        {
            "$vectorSearch": {
                "index": PATTERN_VECTOR_INDEX,
                "path": "vector",
                "queryVector": query_vector,
                "numCandidates": fetch_limit,
                "limit": fetch_limit,
                "filter": {"enabled": True},
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "predictedNext": 1,
                "baseConfidence": 1,
                "structuralCategory": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.patterns.aggregate(pipeline)
    raw_hits = await cursor.to_list(length=fetch_limit)
    live_categories = compatible_categories(window)
    eligible = [h for h in raw_hits if h.get("structuralCategory") in live_categories]
    return eligible[:top_k]


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
    raw_hits = await vector_search_patterns(query_vector, settings.top_k, window)

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

    # Tie detection: among the still-eligible candidates, any whose score is
    # within `pattern_tie_epsilon` of the top pick represents a genuine,
    # honestly-reported ambiguity (e.g. an early window that is equally
    # consistent with "long run" and "long run, broken then resumed" - both
    # of which may still legitimately predict the same next outcome) rather
    # than a confident single answer. Surfaced on the top match so the UI
    # can show it without hiding the other candidates entirely.
    if len(top_matches) >= 2:
        top_score = top_matches[0].score
        also_consistent = [
            m.name
            for m in top_matches[1:]
            if (top_score - m.score) <= settings.pattern_tie_epsilon
        ]
        if also_consistent:
            top_matches[0].alsoConsistentWith = also_consistent

    no_match = len(top_matches) == 0

    # The formal recommendation panel only ever shows a single pick (the
    # Debug Inspector is where the rest of the eligible candidate ranking
    # can be inspected) - alsoConsistentWith above already captured any
    # genuine tie against the rest of the (still size-top_k) eligible pool
    # before we cut down to just the winner here.
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
