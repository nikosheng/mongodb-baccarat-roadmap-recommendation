from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import AllRoads, RandomizeRequest, RoundCreateRequest
from app.services import shoe_service
from app.services.broadcaster import manager
from app.services.derived_match_engine import match_derived
from app.services.derived_roads import compute_all_roads
from app.services.match_engine import match_window
from app.services.side_bet_engine import compute_side_bet_match

router = APIRouter(prefix="/api/shoes", tags=["shoes"])


def _serialize(doc: dict) -> dict:
    out = dict(doc)
    out.pop("_id", None)
    return out


@router.post("")
async def create_shoe(table_id: str = "DEMO_T1"):
    doc = await shoe_service.create_shoe(table_id)
    return _serialize(doc)


@router.get("/{shoe_id}")
async def get_shoe(shoe_id: str):
    doc = await shoe_service.get_shoe(shoe_id)
    if not doc:
        raise HTTPException(status_code=404, detail="shoe not found")
    return _serialize(doc)


@router.post("/{shoe_id}/close")
async def close_shoe(shoe_id: str):
    doc = await shoe_service.close_shoe(shoe_id)
    if not doc:
        raise HTTPException(status_code=404, detail="shoe not found")
    return _serialize(doc)


@router.get("/{shoe_id}/rounds")
async def get_rounds(shoe_id: str):
    rounds = await shoe_service.get_rounds(shoe_id)
    return [_serialize(r) for r in rounds]


async def _push_and_record(shoe_id: str, round_doc: dict, table_id: str) -> dict | None:
    match_result = await match_window(shoe_id, round_doc["roundNo"])
    derived_result = await match_derived(shoe_id, round_doc["roundNo"])

    # Side Bet only ever runs off real-card rounds (manual B/P/T has no
    # card face data to build a feature window from).
    side_bet_result = None
    if round_doc.get("source") == "random_sim":
        side_bet_result = await compute_side_bet_match(shoe_id, round_doc["roundNo"])

    if match_result is None and derived_result is None and side_bet_result is None:
        return None

    payload: dict = {
        "type": "match",
        "shoeId": shoe_id,
        "roundNo": round_doc["roundNo"],
    }
    if match_result is not None:
        payload.update(match_result.model_dump())
    if derived_result is not None:
        payload["derivedMatch"] = derived_result.model_dump()
    if side_bet_result is not None:
        payload["sideBetMatch"] = side_bet_result.model_dump()

    await manager.broadcast(table_id, payload)
    return payload


@router.post("/{shoe_id}/rounds")
async def add_round(shoe_id: str, req: RoundCreateRequest):
    shoe = await shoe_service.get_shoe(shoe_id)
    if not shoe:
        raise HTTPException(status_code=404, detail="shoe not found")

    round_doc = await shoe_service.add_round(shoe_id, req.result)
    match_payload = await _push_and_record(shoe_id, round_doc, shoe["tableId"])

    return {
        "round": _serialize(round_doc),
        "match": match_payload,
    }


@router.post("/{shoe_id}/randomize")
async def randomize(shoe_id: str, req: RandomizeRequest):
    shoe = await shoe_service.get_shoe(shoe_id)
    if not shoe:
        raise HTTPException(status_code=404, detail="shoe not found")

    rounds = await shoe_service.randomize_rounds(shoe_id, req.n)
    last_match = None
    for r in rounds:
        last_match = await _push_and_record(shoe_id, r, shoe["tableId"])

    return {
        "rounds": [_serialize(r) for r in rounds],
        "lastMatch": last_match,
        # True when fewer hands were dealt than requested because the
        # physical shoe passed its cut-card; the shoe must be closed and a
        # new one started to keep dealing (never reshuffled mid-shoe).
        "pastCutCard": shoe_service.is_shoe_past_cut_card(shoe_id),
    }


@router.get("/{shoe_id}/matches")
async def get_matches(shoe_id: str, limit: int = 50):
    matches = await shoe_service.get_matches(shoe_id, limit)
    return [_serialize(m) for m in matches]


@router.get("/{shoe_id}/roads", response_model=AllRoads)
async def get_roads(shoe_id: str):
    shoe = await shoe_service.get_shoe(shoe_id)
    if not shoe:
        raise HTTPException(status_code=404, detail="shoe not found")
    rounds = await shoe_service.get_rounds(shoe_id)
    results = [r["result"] for r in rounds]
    roads = compute_all_roads(results)
    return AllRoads(
        bigRoad=[vars(c) for c in roads.bigRoad],
        bigEye=[vars(c) for c in roads.bigEye],
        small=[vars(c) for c in roads.small],
        cockroach=[vars(c) for c in roads.cockroach],
    )


@router.get("/{shoe_id}/derived-matches")
async def get_derived_matches(shoe_id: str, limit: int = 50):
    db_matches = await shoe_service.get_derived_matches(shoe_id, limit)
    return [_serialize(m) for m in db_matches]


@router.get("/{shoe_id}/side-bet-matches")
async def get_side_bet_matches(shoe_id: str, limit: int = 50):
    db_matches = await shoe_service.get_side_bet_matches(shoe_id, limit)
    return [_serialize(m) for m in db_matches]
