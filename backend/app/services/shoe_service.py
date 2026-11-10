"""Shoe lifecycle + round ingestion business logic."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models.schemas import Outcome, Round, Shoe
from app.services import baccarat_dealer


def new_shoe_id() -> str:
    return f"shoe_{uuid.uuid4().hex[:10]}"


async def create_shoe(table_id: str = "DEMO_T1") -> dict:
    db = get_db()
    shoe = Shoe(shoeId=new_shoe_id(), tableId=table_id)
    doc = shoe.model_dump()
    await db.shoes.insert_one(doc)
    # A new logical shoe always starts a freshly shuffled 8-deck physical
    # shoe for the real-card dealer (randomize_rounds); manual B/P/T entry
    # never touches this deck state.
    baccarat_dealer.start_dealer_shoe(shoe.shoeId)
    return doc


async def get_shoe(shoe_id: str) -> dict | None:
    db = get_db()
    return await db.shoes.find_one({"shoeId": shoe_id})


async def close_shoe(shoe_id: str) -> dict | None:
    db = get_db()
    now = datetime.now(timezone.utc)
    await db.shoes.update_one(
        {"shoeId": shoe_id}, {"$set": {"status": "closed", "endedAt": now}}
    )
    baccarat_dealer.discard_dealer_shoe(shoe_id)
    return await get_shoe(shoe_id)


async def _insert_round(shoe_id: str, round_model: Round) -> dict:
    db = get_db()
    round_doc = round_model.model_dump()
    await db.rounds.insert_one(round_doc)

    summary_key = f"summary.{round_model.result}"
    await db.shoes.update_one(
        {"shoeId": shoe_id},
        {"$inc": {"totalRounds": 1, summary_key: 1}},
    )
    return round_doc


async def add_round(shoe_id: str, result: Outcome, source: str = "manual_sim") -> dict:
    """Manual B/P/T entry. These rounds have no card face data (see
    docs/side-bet-lucky6-plan.md §3.2) and must never be used as Side Bet
    feature inputs."""
    shoe = await get_shoe(shoe_id)
    if shoe is None:
        raise ValueError(f"shoe not found: {shoe_id}")

    next_round_no = shoe["totalRounds"] + 1
    round_model = Round(shoeId=shoe_id, roundNo=next_round_no, result=result, source=source)
    return await _insert_round(shoe_id, round_model)


def _hand_to_round(shoe_id: str, round_no: int, hand: baccarat_dealer.HandResult) -> Round:
    return Round(
        shoeId=shoe_id,
        roundNo=round_no,
        result=hand.result,
        source="random_sim",
        bankerCards=[c.to_dict() for c in hand.bankerCards],
        playerCards=[c.to_dict() for c in hand.playerCards],
        bankerTotal=hand.bankerTotal,
        playerTotal=hand.playerTotal,
        margin=hand.margin,
        bankerCardCount=hand.bankerCardCount,
        playerCardCount=hand.playerCardCount,
        totalCardCount=hand.totalCardCount,
        bankerPair=hand.bankerPair,
        playerPair=hand.playerPair,
        bankerPerfectPair=hand.bankerPerfectPair,
        playerPerfectPair=hand.playerPerfectPair,
        naturalType=hand.naturalType,
        lucky6Result=hand.lucky6Result,
    )


async def randomize_rounds(shoe_id: str, n: int) -> list[dict]:
    """Deal up to `n` real hands from this shoe's persistent dealer deck.
    If the shoe passes its cut-card partway through, dealing stops early
    (the deck is never reshuffled mid-shoe) and only the hands actually
    dealt are returned/persisted."""
    shoe = await get_shoe(shoe_id)
    if shoe is None:
        raise ValueError(f"shoe not found: {shoe_id}")

    dealer = baccarat_dealer.get_dealer_shoe(shoe_id)
    if dealer is None:
        # Backend restarted or shoe predates this feature: start a fresh
        # physical deck rather than fail the request.
        dealer = baccarat_dealer.start_dealer_shoe(shoe_id)

    out = []
    next_round_no = shoe["totalRounds"] + 1
    for i in range(n):
        if not dealer.can_deal_hand():
            break
        hand = dealer.deal_hand()
        round_model = _hand_to_round(shoe_id, next_round_no + i, hand)
        out.append(await _insert_round(shoe_id, round_model))
    return out


def is_shoe_past_cut_card(shoe_id: str) -> bool:
    dealer = baccarat_dealer.get_dealer_shoe(shoe_id)
    if dealer is None:
        return False
    return not dealer.can_deal_hand()


async def get_rounds(shoe_id: str) -> list[dict]:
    db = get_db()
    cursor = db.rounds.find({"shoeId": shoe_id}).sort("roundNo", 1)
    return await cursor.to_list(length=None)


async def get_matches(shoe_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    cursor = db.matches.find({"shoeId": shoe_id}).sort("roundNo", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_derived_matches(shoe_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    cursor = db.derived_matches.find({"shoeId": shoe_id}).sort("roundNo", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_side_bet_matches(shoe_id: str, limit: int = 50) -> list[dict]:
    db = get_db()
    cursor = (
        db.side_bet_matches.find({"shoeId": shoe_id}).sort("sourceRoundNo", -1).limit(limit)
    )
    return await cursor.to_list(length=limit)
