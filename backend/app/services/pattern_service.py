"""Pattern CRUD + embedding lifecycle. Ensures every write path (create,
update canonicalSequence) re-runs describe_window_in_nl + embed so the
stored vector always matches the current NL_DESCRIBER_VERSION."""

from __future__ import annotations

import numpy as np
from bson import ObjectId
from bson.errors import InvalidId

from app.config import get_settings
from app.db import PATTERN_VECTOR_INDEX, get_db
from app.models.schemas import (
    EmbedPreviewResponse,
    PatternCreateRequest,
    PatternUpdateRequest,
    SimilarPatternHit,
)
from app.services.embedder import embed_text
from app.services.pattern_structure import classify_structure
from app.services.window_text import describe_window_in_nl


def expand_sequence(canonical: str) -> list[str]:
    seq = list(canonical.strip().upper())
    bad = [c for c in seq if c not in ("B", "P", "T")]
    if bad:
        raise ValueError(f"invalid characters in canonicalSequence: {bad}")
    return seq


def infer_min_window_len(canonical_seq: list[str]) -> int:
    return len(canonical_seq)


def infer_structural_category(canonical_seq: list[str]) -> str:
    """Classify a pattern's canonicalSequence into a coarse narrative shape
    (see pattern_structure.py). Stored on every pattern so match_engine can
    cheaply filter candidates by structural compatibility with the live
    window instead of a raw length cutoff."""
    return classify_structure(canonical_seq)


async def build_embedding_payload(canonical_sequence: str) -> EmbedPreviewResponse:
    seq = expand_sequence(canonical_sequence)
    text = describe_window_in_nl(seq)
    vector = await embed_text(text, mode="document")
    norm = float(np.linalg.norm(vector))
    return EmbedPreviewResponse(
        textForEmbedding=text,
        vectorPreview=vector[:16],
        vectorDim=len(vector),
        vectorNorm=round(norm, 4),
    )


async def create_pattern(req: PatternCreateRequest) -> dict:
    from datetime import datetime, timezone

    settings = get_settings()
    db = get_db()

    seq = expand_sequence(req.canonicalSequence)
    text = describe_window_in_nl(seq)
    vector = await embed_text(text, mode="document")

    now = datetime.now(timezone.utc)
    doc = {
        "name": req.name,
        "category": req.category,
        "nlDescription": req.nlDescription,
        "canonicalSequence": req.canonicalSequence.strip().upper(),
        "minWindowLen": infer_min_window_len(seq),
        "structuralCategory": infer_structural_category(seq),
        "predictedNext": req.predictedNext,
        "baseConfidence": req.baseConfidence,
        "textForEmbedding": text,
        "textVersion": settings.nl_describer_version,
        "vector": vector,
        "enabled": req.enabled,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db.patterns.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def update_pattern(pattern_id: str, req: PatternUpdateRequest) -> dict | None:
    from datetime import datetime, timezone

    settings = get_settings()
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return None

    existing = await db.patterns.find_one({"_id": oid})
    if not existing:
        return None

    update_fields = {k: v for k, v in req.model_dump(exclude_unset=True).items()}

    # If canonicalSequence changed, re-derive text + re-embed
    if "canonicalSequence" in update_fields:
        seq = expand_sequence(update_fields["canonicalSequence"])
        text = describe_window_in_nl(seq)
        vector = await embed_text(text, mode="document")
        update_fields["canonicalSequence"] = update_fields["canonicalSequence"].strip().upper()
        update_fields["minWindowLen"] = infer_min_window_len(seq)
        update_fields["structuralCategory"] = infer_structural_category(seq)
        update_fields["textForEmbedding"] = text
        update_fields["textVersion"] = settings.nl_describer_version
        update_fields["vector"] = vector

    update_fields["updatedAt"] = datetime.now(timezone.utc)

    await db.patterns.update_one({"_id": oid}, {"$set": update_fields})
    return await db.patterns.find_one({"_id": oid})


async def delete_pattern(pattern_id: str) -> bool:
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return False
    result = await db.patterns.delete_one({"_id": oid})
    return result.deleted_count > 0


async def list_patterns(category: str | None = None, enabled: bool | None = None) -> list[dict]:
    db = get_db()
    query: dict = {}
    if category:
        query["category"] = category
    if enabled is not None:
        query["enabled"] = enabled
    cursor = db.patterns.find(query).sort("createdAt", 1)
    return await cursor.to_list(length=None)


async def get_pattern(pattern_id: str) -> dict | None:
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return None
    return await db.patterns.find_one({"_id": oid})


async def similarity_check(canonical_sequence: str, exclude_pattern_id: str | None = None) -> list[SimilarPatternHit]:
    """Find existing patterns semantically close to a candidate sequence,
    used by the admin UI to warn about near-duplicate patterns."""
    db = get_db()
    seq = expand_sequence(canonical_sequence)
    text = describe_window_in_nl(seq)
    vector = await embed_text(text, mode="query")

    pipeline = [
        {
            "$vectorSearch": {
                "index": PATTERN_VECTOR_INDEX,
                "path": "vector",
                "queryVector": vector,
                "numCandidates": 50,
                "limit": 10,
                "filter": {"enabled": True},
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.patterns.aggregate(pipeline)
    hits = await cursor.to_list(length=10)

    results = []
    for h in hits:
        pid = str(h["_id"])
        if exclude_pattern_id and pid == exclude_pattern_id:
            continue
        results.append(SimilarPatternHit(patternId=pid, name=h["name"], score=round(h["score"], 4)))
    return results


def serialize_pattern(doc: dict) -> dict:
    out = dict(doc)
    out["_id"] = str(out["_id"])
    out.pop("vector", None)  # don't ship full 1024-d vector in normal list responses
    return out
