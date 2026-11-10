"""Live Side Bet (Lucky 6) search engine (see
docs/side-bet-lucky6-plan.md §7).

After a real-card round completes, builds the current `SIDE_BET_WINDOW`-hand
query vector (same `side_bet_features` encoder used at seed time), runs
`$vectorSearch` against `side_bet_slices` filtered to the configured
windowLength/datasetType/corpusVersion, de-duplicates neighbors by shoeId
(so Top K means K distinct historical shoes, never K overlapping windows
from the same shoe), and reports the neighborhood's next-hand Lucky 6 rates
against the matching corpus baseline as a lift — or an explicit
"insufficient data" / "insufficient samples" reason instead of a misleading
number.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import SIDE_BET_VECTOR_INDEX, get_db
from app.models.schemas import SideBetMatchResult
from app.services.side_bet_features import (
    InsufficientWindowError,
    WindowRound,
    extract_raw_features,
    zscore,
)

logger = logging.getLogger(__name__)

_FACE_RANKS = {"10", "J", "Q", "K"}


def _face_card_count(cards: list[dict]) -> int:
    return sum(1 for c in cards if c.get("rank") in _FACE_RANKS)


def _round_doc_to_window_round(round_doc: dict) -> WindowRound | None:
    """None if this round has no card face data (manual B/P/T entry) — such
    a round can never be part of a Side Bet feature window."""
    if round_doc.get("source") != "random_sim":
        return None
    if round_doc.get("bankerCards") is None or round_doc.get("playerCards") is None:
        return None
    return WindowRound(
        result=round_doc["result"],
        margin=round_doc["margin"],
        totalCardCount=round_doc["totalCardCount"],
        bankerPair=round_doc["bankerPair"],
        playerPair=round_doc["playerPair"],
        faceCardCount=(
            _face_card_count(round_doc["bankerCards"]) + _face_card_count(round_doc["playerCards"])
        ),
    )


async def get_recent_card_window(shoe_id: str, window_length: int) -> list[WindowRound] | None:
    """Fetch the most recent `window_length` rounds for `shoe_id`. Returns
    None (insufficient data) if there aren't yet `window_length` rounds, if
    the round numbers aren't contiguous (shouldn't happen within one shoe,
    but guarded defensively), or if any round in that span lacks card face
    data (a manual B/P/T entry breaks the window — it is never padded or
    guessed)."""
    db = get_db()
    cursor = db.rounds.find({"shoeId": shoe_id}).sort("roundNo", -1).limit(window_length)
    docs = await cursor.to_list(length=window_length)
    if len(docs) < window_length:
        return None
    docs.reverse()

    expected_round_no = docs[0]["roundNo"]
    window_rounds: list[WindowRound] = []
    for doc in docs:
        if doc["roundNo"] != expected_round_no:
            return None
        expected_round_no += 1
        wr = _round_doc_to_window_round(doc)
        if wr is None:
            return None
        window_rounds.append(wr)
    return window_rounds


async def get_stats(window_length: int, feature_version: str, corpus_version: str) -> dict | None:
    db = get_db()
    return await db.side_bet_stats.find_one(
        {"windowLength": window_length, "featureVersion": feature_version, "corpusVersion": corpus_version}
    )


async def get_baseline(window_length: int, dataset_type: str, corpus_version: str) -> dict | None:
    db = get_db()
    return await db.side_bet_baselines.find_one(
        {"windowLength": window_length, "datasetType": dataset_type, "corpusVersion": corpus_version}
    )


async def vector_search_slices(
    query_vector: list[float],
    window_length: int,
    dataset_type: str,
    corpus_version: str,
    top_k: int,
    candidate_multiplier: int,
) -> list[dict]:
    """Over-fetch candidates (more than top_k) because multiple overlapping
    windows from the same historical shoe can all score highly; we need
    enough raw hits left after per-shoe dedup to still reach top_k distinct
    shoes when possible."""
    db = get_db()
    num_candidates = max(top_k * candidate_multiplier, top_k)
    pipeline = [
        {
            "$vectorSearch": {
                "index": SIDE_BET_VECTOR_INDEX,
                "path": "vector",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": num_candidates,
                "filter": {
                    "windowLength": window_length,
                    "datasetType": dataset_type,
                    "corpusVersion": corpus_version,
                },
            }
        },
        {
            "$project": {
                "_id": 1,
                "shoeId": 1,
                "nextLucky6Result": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db.side_bet_slices.aggregate(pipeline)
    return await cursor.to_list(length=num_candidates)


def _dedupe_by_shoe(hits: list[dict], top_k: int) -> list[dict]:
    """Atlas returns hits ordered by score descending; keep at most one per
    shoeId (the first, i.e. highest-scoring, occurrence) so Top K means K
    distinct historical shoes."""
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        shoe_id = h["shoeId"]
        if shoe_id in seen:
            continue
        seen.add(shoe_id)
        out.append(h)
        if len(out) >= top_k:
            break
    return out


def _lift(rate: float | None, baseline: float | None) -> float | None:
    if rate is None or baseline is None or baseline == 0:
        return None
    return rate / baseline


async def _persist(result: SideBetMatchResult) -> None:
    db = get_db()
    await db.side_bet_matches.insert_one(result.model_dump())


async def compute_side_bet_match(shoe_id: str, source_round_no: int) -> SideBetMatchResult:
    """Full pipeline for the hand that just completed at `source_round_no`:
    fetch window -> raw features -> z-score with this N's fixed corpus
    mean/std -> $vectorSearch -> dedupe by shoe -> neighborhood rate vs
    baseline -> lift. Always persists (and returns) a SideBetMatchResult,
    even when `insufficientData` — so the UI always has something to show
    and why."""
    settings = get_settings()
    settings.validate_side_bet_window()
    window_length = settings.side_bet_window
    dataset_type = settings.side_bet_dataset
    corpus_version = settings.side_bet_corpus_version
    feature_version = settings.side_bet_feature_version

    base = dict(
        shoeId=shoe_id,
        sourceRoundNo=source_round_no,
        predictionForRoundNo=source_round_no + 1,
        windowLength=window_length,
        datasetType=dataset_type,
        corpusVersion=corpus_version,
        featureVersion=feature_version,
    )

    window_rounds = await get_recent_card_window(shoe_id, window_length)
    if window_rounds is None:
        result = SideBetMatchResult(
            **base,
            insufficientData=True,
            reason=(
                f"需要最近 {window_length} 手連續、同一靴且皆有牌面資料的完整紀錄"
                "(手動輸入的 B/P/T 沒有牌面,無法納入窗口)"
            ),
        )
        await _persist(result)
        return result

    stats = await get_stats(window_length, feature_version, corpus_version)
    baseline = await get_baseline(window_length, dataset_type, corpus_version)
    if stats is None or baseline is None:
        result = SideBetMatchResult(
            **base,
            insufficientData=True,
            reason=f"尚未為 N={window_length}/{dataset_type} seed 統計或 baseline,請先執行 make seed-sidebets",
        )
        await _persist(result)
        return result

    try:
        raw_features = extract_raw_features(window_rounds, window_length)
    except InsufficientWindowError as exc:
        result = SideBetMatchResult(**base, insufficientData=True, reason=str(exc))
        await _persist(result)
        return result

    query_vector = zscore(raw_features, stats["mean"], stats["std"])

    raw_hits = await vector_search_slices(
        query_vector,
        window_length,
        dataset_type,
        corpus_version,
        settings.side_bet_top_k,
        settings.side_bet_candidate_multiplier,
    )
    neighbors = _dedupe_by_shoe(raw_hits, settings.side_bet_top_k)

    if not neighbors:
        result = SideBetMatchResult(
            **base,
            insufficientData=True,
            reason="向量搜尋沒有回傳任何歷史切片鄰居,請確認已執行 make seed-sidebets 且 index 已 queryable",
        )
        await _persist(result)
        return result

    neighbor_count = len(neighbors)
    top_similarity_score = round(neighbors[0]["score"], 4)

    two_hits = sum(1 for h in neighbors if h["nextLucky6Result"] == "banker_6_two_cards")
    three_hits = sum(1 for h in neighbors if h["nextLucky6Result"] == "banker_6_three_cards")
    two_rate = two_hits / neighbor_count
    three_rate = three_hits / neighbor_count

    enough_samples = neighbor_count >= settings.side_bet_min_samples_for_lift

    two_baseline = baseline.get("lucky6TwoCardRate")
    three_baseline = baseline.get("lucky6ThreeCardRate")

    two_lift = _lift(two_rate, two_baseline) if enough_samples else None
    three_lift = _lift(three_rate, three_baseline) if enough_samples else None

    result = SideBetMatchResult(
        **base,
        topSimilarityScore=top_similarity_score,
        neighborCount=neighbor_count,
        reason=None if enough_samples else "樣本不足:鄰居數過少,lift 僅供參考不予顯示",
        lucky6TwoCardHits=two_hits,
        lucky6TwoCardRate=round(two_rate, 4),
        lucky6TwoCardBaseline=round(two_baseline, 4) if two_baseline is not None else None,
        lucky6TwoCardLift=round(two_lift, 4) if two_lift is not None else None,
        lucky6ThreeCardHits=three_hits,
        lucky6ThreeCardRate=round(three_rate, 4),
        lucky6ThreeCardBaseline=round(three_baseline, 4) if three_baseline is not None else None,
        lucky6ThreeCardLift=round(three_lift, 4) if three_lift is not None else None,
    )
    await _persist(result)
    return result
