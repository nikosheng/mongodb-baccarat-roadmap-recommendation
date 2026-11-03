"""Debug endpoints: full pattern cosine ranking (not just top-K) and the
exact NL text used for both the current window and each pattern, so the
vector search pipeline is fully transparent for demo purposes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import DERIVED_PATTERN_VECTOR_INDEX, PATTERN_VECTOR_INDEX, get_db
from app.services.derived_roads import compute_all_roads, describe_derived_in_nl, extract_tail_symbols
from app.services.embedder import embed_text
from app.services.shoe_service import get_rounds, get_shoe
from app.services.window_text import compute_window_stats, describe_window_in_nl
from app.config import get_settings

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/windows/{shoe_id}/{round_no}")
async def window_detail(shoe_id: str, round_no: int):
    settings = get_settings()
    shoe = await get_shoe(shoe_id)
    if not shoe:
        raise HTTPException(status_code=404, detail="shoe not found")

    all_rounds = await get_rounds(shoe_id)
    upto = [r for r in all_rounds if r["roundNo"] <= round_no]
    if not upto:
        raise HTTPException(status_code=404, detail="round not found")

    window = [r["result"] for r in upto[-settings.max_window :]]

    if len(window) < settings.min_window_for_match:
        return {
            "shoeId": shoe_id,
            "roundNo": round_no,
            "window": "".join(window),
            "insufficientRounds": True,
            "minWindowForMatch": settings.min_window_for_match,
        }

    text = describe_window_in_nl(window)
    stats = compute_window_stats(window)
    query_vector = await embed_text(text, mode="query")

    db = get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": PATTERN_VECTOR_INDEX,
                "path": "vector",
                "queryVector": query_vector,
                "numCandidates": 200,
                "limit": 50,  # effectively "all" patterns for a demo-scale library
                "filter": {"enabled": True},
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "category": 1,
                "predictedNext": 1,
                "baseConfidence": 1,
                "textForEmbedding": 1,
                "canonicalSequence": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.patterns.aggregate(pipeline)
    all_ranked = await cursor.to_list(length=50)

    for r in all_ranked:
        r["_id"] = str(r["_id"])
        r["score"] = round(r["score"], 4)

    gaps = []
    for i in range(len(all_ranked) - 1):
        gaps.append(round(all_ranked[i]["score"] - all_ranked[i + 1]["score"], 4))

    return {
        "shoeId": shoe_id,
        "roundNo": round_no,
        "window": "".join(window),
        "windowText": text,
        "windowStats": {
            "length": stats.length,
            "counts": stats.counts,
            "ratios": {k: round(v, 3) for k, v in stats.ratios.items()},
            "maxStreak": stats.max_streak,
            "currentStreakType": stats.current_streak_type,
            "currentStreakLen": stats.current_streak_len,
            "chopCount": stats.chop_count,
            "reversal": stats.reversal,
            "rhythm": stats.rhythm,
        },
        "queryVectorPreview": query_vector[:16],
        "queryVectorNorm": round(sum(v * v for v in query_vector) ** 0.5, 4),
        "threshold": settings.pattern_min_score,
        "ranking": all_ranked,
        "gaps": gaps,
    }


@router.get("/derived/{shoe_id}/{round_no}")
async def derived_window_detail(shoe_id: str, round_no: int):
    settings = get_settings()
    shoe = await get_shoe(shoe_id)
    if not shoe:
        raise HTTPException(status_code=404, detail="shoe not found")

    all_rounds = await get_rounds(shoe_id)
    upto = [r for r in all_rounds if r["roundNo"] <= round_no]
    if not upto:
        raise HTTPException(status_code=404, detail="round not found")

    results = [r["result"] for r in upto]
    roads = compute_all_roads(results)
    tail = extract_tail_symbols(roads, k=settings.derived_tail_length)

    if not (tail.bigEye or tail.small or tail.cockroach):
        return {
            "shoeId": shoe_id,
            "roundNo": round_no,
            "insufficientColumns": True,
        }

    text = describe_derived_in_nl(tail)
    query_vector = await embed_text(text, mode="query")

    db = get_db()
    pipeline = [
        {
            "$vectorSearch": {
                "index": DERIVED_PATTERN_VECTOR_INDEX,
                "path": "vector",
                "queryVector": query_vector,
                "numCandidates": 200,
                "limit": 50,
                "filter": {"enabled": True},
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "category": 1,
                "predictedNext": 1,
                "baseConfidence": 1,
                "textForEmbedding": 1,
                "canonicalRoads": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.derived_patterns.aggregate(pipeline)
    all_ranked = await cursor.to_list(length=50)

    for r in all_ranked:
        r["_id"] = str(r["_id"])
        r["score"] = round(r["score"], 4)

    gaps = []
    for i in range(len(all_ranked) - 1):
        gaps.append(round(all_ranked[i]["score"] - all_ranked[i + 1]["score"], 4))

    return {
        "shoeId": shoe_id,
        "roundNo": round_no,
        "tailSymbols": {"bigEye": tail.bigEye, "small": tail.small, "cockroach": tail.cockroach},
        "derivedText": text,
        "queryVectorPreview": query_vector[:16],
        "queryVectorNorm": round(sum(v * v for v in query_vector) ** 0.5, 4),
        "threshold": settings.derived_pattern_min_score,
        "ranking": all_ranked,
        "gaps": gaps,
    }
