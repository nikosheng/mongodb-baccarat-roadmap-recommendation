from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    DerivedEmbedPreviewRequest,
    DerivedNLParseRequest,
    DerivedPatternCreateRequest,
    DerivedPatternUpdateRequest,
    DerivedSimilarityCheckRequest,
)
from app.services import derived_pattern_service
from app.services.nl_derived_pattern import DerivedNLParseError, parse_nl_derived_pattern

router = APIRouter(prefix="/api/derived-patterns", tags=["derived-patterns"])


@router.get("")
async def list_derived_patterns(category: str | None = None, enabled: bool | None = None):
    docs = await derived_pattern_service.list_derived_patterns(category, enabled)
    return [derived_pattern_service.serialize_derived_pattern(d) for d in docs]


@router.get("/{pattern_id}")
async def get_derived_pattern(pattern_id: str):
    doc = await derived_pattern_service.get_derived_pattern(pattern_id)
    if not doc:
        raise HTTPException(status_code=404, detail="derived pattern not found")
    return derived_pattern_service.serialize_derived_pattern(doc)


@router.post("")
async def create_derived_pattern(req: DerivedPatternCreateRequest):
    try:
        doc = await derived_pattern_service.create_derived_pattern(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return derived_pattern_service.serialize_derived_pattern(doc)


@router.put("/{pattern_id}")
async def update_derived_pattern(pattern_id: str, req: DerivedPatternUpdateRequest):
    try:
        doc = await derived_pattern_service.update_derived_pattern(pattern_id, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not doc:
        raise HTTPException(status_code=404, detail="derived pattern not found")
    return derived_pattern_service.serialize_derived_pattern(doc)


@router.delete("/{pattern_id}")
async def delete_derived_pattern(pattern_id: str):
    ok = await derived_pattern_service.delete_derived_pattern(pattern_id)
    if not ok:
        raise HTTPException(status_code=404, detail="derived pattern not found")
    return {"deleted": True}


@router.post("/nl")
async def parse_nl(req: DerivedNLParseRequest):
    try:
        result = await parse_nl_derived_pattern(req.text)
    except DerivedNLParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/embed-preview")
async def embed_preview(req: DerivedEmbedPreviewRequest):
    try:
        result = await derived_pattern_service.build_embedding_payload(req.canonicalRoads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/similarity-check")
async def similarity_check(req: DerivedSimilarityCheckRequest):
    try:
        hits = await derived_pattern_service.similarity_check(req.canonicalRoads, req.excludePatternId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"hits": [h.model_dump() for h in hits]}
