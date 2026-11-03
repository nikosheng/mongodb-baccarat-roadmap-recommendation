"""Shoe lifecycle + round ingestion business logic."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models.schemas import Outcome, Round, Shoe

# Real baccarat outcome probabilities (8-deck shoe, standard rules)
BACCARAT_PROBS: dict[Outcome, float] = {"B": 0.4586, "P": 0.4462, "T": 0.0952}


def new_shoe_id() -> str:
    return f"shoe_{uuid.uuid4().hex[:10]}"


async def create_shoe(table_id: str = "DEMO_T1") -> dict:
    db = get_db()
    shoe = Shoe(shoeId=new_shoe_id(), tableId=table_id)
    doc = shoe.model_dump()
    await db.shoes.insert_one(doc)
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
    return await get_shoe(shoe_id)


async def add_round(shoe_id: str, result: Outcome, source: str = "manual_sim") -> dict:
    db = get_db()
    shoe = await get_shoe(shoe_id)
    if shoe is None:
        raise ValueError(f"shoe not found: {shoe_id}")

    next_round_no = shoe["totalRounds"] + 1
    round_doc = Round(
        shoeId=shoe_id, roundNo=next_round_no, result=result, source=source
    ).model_dump()
    await db.rounds.insert_one(round_doc)

    summary_key = f"summary.{result}"
    await db.shoes.update_one(
        {"shoeId": shoe_id},
        {"$inc": {"totalRounds": 1, summary_key: 1}},
    )
    return round_doc


def random_outcome() -> Outcome:
    r = random.random()
    cumulative = 0.0
    for outcome, p in BACCARAT_PROBS.items():
        cumulative += p
        if r <= cumulative:
            return outcome
    return "B"


async def randomize_rounds(shoe_id: str, n: int) -> list[dict]:
    out = []
    for _ in range(n):
        result = random_outcome()
        out.append(await add_round(shoe_id, result, source="random_sim"))
    return out


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
