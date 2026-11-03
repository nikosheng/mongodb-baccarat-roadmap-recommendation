from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    EmbedPreviewRequest,
    NLParseRequest,
    PatternCreateRequest,
    PatternUpdateRequest,
    SimilarityCheckRequest,
)
from app.services import pattern_service
from app.services.nl_pattern import NLParseError, parse_nl_pattern

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


@router.get("")
async def list_patterns(category: str | None = None, enabled: bool | None = None):
    docs = await pattern_service.list_patterns(category, enabled)
    return [pattern_service.serialize_pattern(d) for d in docs]


@router.get("/{pattern_id}")
async def get_pattern(pattern_id: str):
    doc = await pattern_service.get_pattern(pattern_id)
    if not doc:
        raise HTTPException(status_code=404, detail="pattern not found")
    return pattern_service.serialize_pattern(doc)


@router.post("")
async def create_pattern(req: PatternCreateRequest):
    try:
        doc = await pattern_service.create_pattern(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return pattern_service.serialize_pattern(doc)


@router.put("/{pattern_id}")
async def update_pattern(pattern_id: str, req: PatternUpdateRequest):
    try:
        doc = await pattern_service.update_pattern(pattern_id, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not doc:
        raise HTTPException(status_code=404, detail="pattern not found")
    return pattern_service.serialize_pattern(doc)


@router.delete("/{pattern_id}")
async def delete_pattern(pattern_id: str):
    ok = await pattern_service.delete_pattern(pattern_id)
    if not ok:
        raise HTTPException(status_code=404, detail="pattern not found")
    return {"deleted": True}


@router.post("/nl")
async def parse_nl(req: NLParseRequest):
    try:
        result = await parse_nl_pattern(req.text)
    except NLParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/embed-preview")
async def embed_preview(req: EmbedPreviewRequest):
    try:
        result = await pattern_service.build_embedding_payload(req.canonicalSequence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/similarity-check")
async def similarity_check(req: SimilarityCheckRequest):
    try:
        hits = await pattern_service.similarity_check(req.canonicalSequence, req.excludePatternId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"hits": [h.model_dump() for h in hits]}
