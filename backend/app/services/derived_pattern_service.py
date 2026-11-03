"""Derived-road (下三路) pattern CRUD + embedding lifecycle. Mirrors
pattern_service.py but keyed on canonicalRoads (three R/B tail-symbol
strings) instead of a B/P/T canonicalSequence."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from bson import ObjectId
from bson.errors import InvalidId

from app.config import get_settings
from app.db import DERIVED_PATTERN_VECTOR_INDEX, get_db
from app.models.schemas import (
    DerivedEmbedPreviewResponse,
    DerivedPatternCreateRequest,
    DerivedPatternUpdateRequest,
    DerivedSimilarPatternHit,
    DerivedTailSymbolsSchema,
)
from app.services.derived_roads import DerivedTailSymbols, describe_derived_in_nl
from app.services.embedder import embed_text


def _to_internal(roads: DerivedTailSymbolsSchema) -> DerivedTailSymbols:
    return DerivedTailSymbols(
        bigEye=roads.bigEye.strip().upper(),
        small=roads.small.strip().upper(),
        cockroach=roads.cockroach.strip().upper(),
    )


def validate_roads(roads: DerivedTailSymbolsSchema) -> DerivedTailSymbols:
    internal = _to_internal(roads)
    for field_name, value in (
        ("bigEye", internal.bigEye),
        ("small", internal.small),
        ("cockroach", internal.cockroach),
    ):
        bad = [c for c in value if c not in ("R", "B")]
        if bad:
            raise ValueError(f"invalid characters in canonicalRoads.{field_name}: {bad}")
    return internal


async def build_embedding_payload(roads: DerivedTailSymbolsSchema) -> DerivedEmbedPreviewResponse:
    internal = validate_roads(roads)
    text = describe_derived_in_nl(internal)
    vector = await embed_text(text, mode="document")
    norm = float(np.linalg.norm(vector))
    return DerivedEmbedPreviewResponse(
        textForEmbedding=text,
        vectorPreview=vector[:16],
        vectorDim=len(vector),
        vectorNorm=round(norm, 4),
    )


def _roads_dict(internal: DerivedTailSymbols) -> dict:
    return {"bigEye": internal.bigEye, "small": internal.small, "cockroach": internal.cockroach}


async def create_derived_pattern(req: DerivedPatternCreateRequest) -> dict:
    settings = get_settings()
    db = get_db()

    internal = validate_roads(req.canonicalRoads)
    text = describe_derived_in_nl(internal)
    vector = await embed_text(text, mode="document")

    now = datetime.now(timezone.utc)
    doc = {
        "name": req.name,
        "category": req.category,
        "nlDescription": req.nlDescription,
        "canonicalRoads": _roads_dict(internal),
        "predictedNext": req.predictedNext,
        "baseConfidence": req.baseConfidence,
        "textForEmbedding": text,
        "textVersion": settings.nl_derived_describer_version,
        "vector": vector,
        "enabled": req.enabled,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db.derived_patterns.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def update_derived_pattern(pattern_id: str, req: DerivedPatternUpdateRequest) -> dict | None:
    settings = get_settings()
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return None

    existing = await db.derived_patterns.find_one({"_id": oid})
    if not existing:
        return None

    update_fields: dict = {}
    data = req.model_dump(exclude_unset=True)

    if "canonicalRoads" in data:
        internal = validate_roads(req.canonicalRoads)  # type: ignore[arg-type]
        text = describe_derived_in_nl(internal)
        vector = await embed_text(text, mode="document")
        update_fields["canonicalRoads"] = _roads_dict(internal)
        update_fields["textForEmbedding"] = text
        update_fields["textVersion"] = settings.nl_derived_describer_version
        update_fields["vector"] = vector
        data.pop("canonicalRoads")

    update_fields.update(data)
    update_fields["updatedAt"] = datetime.now(timezone.utc)

    await db.derived_patterns.update_one({"_id": oid}, {"$set": update_fields})
    return await db.derived_patterns.find_one({"_id": oid})


async def delete_derived_pattern(pattern_id: str) -> bool:
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return False
    result = await db.derived_patterns.delete_one({"_id": oid})
    return result.deleted_count > 0


async def list_derived_patterns(category: str | None = None, enabled: bool | None = None) -> list[dict]:
    db = get_db()
    query: dict = {}
    if category:
        query["category"] = category
    if enabled is not None:
        query["enabled"] = enabled
    cursor = db.derived_patterns.find(query).sort("createdAt", 1)
    return await cursor.to_list(length=None)


async def get_derived_pattern(pattern_id: str) -> dict | None:
    db = get_db()
    try:
        oid = ObjectId(pattern_id)
    except InvalidId:
        return None
    return await db.derived_patterns.find_one({"_id": oid})


async def similarity_check(
    roads: DerivedTailSymbolsSchema, exclude_pattern_id: str | None = None
) -> list[DerivedSimilarPatternHit]:
    db = get_db()
    internal = validate_roads(roads)
    text = describe_derived_in_nl(internal)
    vector = await embed_text(text, mode="query")

    pipeline = [
        {
            "$vectorSearch": {
                "index": DERIVED_PATTERN_VECTOR_INDEX,
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
    cursor = db.derived_patterns.aggregate(pipeline)
    hits = await cursor.to_list(length=10)

    results = []
    for h in hits:
        pid = str(h["_id"])
        if exclude_pattern_id and pid == exclude_pattern_id:
            continue
        results.append(DerivedSimilarPatternHit(patternId=pid, name=h["name"], score=round(h["score"], 4)))
    return results


def serialize_derived_pattern(doc: dict) -> dict:
    out = dict(doc)
    out["_id"] = str(out["_id"])
    out.pop("vector", None)
    return out
