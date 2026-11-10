"""Monte Carlo + demo fixture seed for the Side Bet (Lucky 6 v1) history
corpus (see docs/side-bet-lucky6-plan.md §6).

Simulates many independent 8-deck shoes with the same real baccarat dealer
used by the live app (`app.services.baccarat_dealer`), slices each shoe's
hand sequence into every supported window length N, extracts the 13 raw
features for each window (`app.services.side_bet_features`), fits N-specific
mean/std from the Monte Carlo corpus only, converts every slice (Monte Carlo
*and* demo) to a z-score vector with that same scaler, and writes
slices/stats/baselines to MongoDB (plus raw per-shoe hand data so future N
values can be re-sliced without resimulating).

This is idempotent for a given (corpusVersion, featureVersion): each run
deletes prior documents tagged with that version before inserting the fresh
batch, so partial/mismatched-scaler data never lingers.

Usage:
    python -m app.seed.seed_side_bet_history

Env overrides (useful for fast local iteration instead of the full 2,000
Monte Carlo shoes):
    SIDE_BET_SEED_SHOE_COUNT   (default 2000)
    SIDE_BET_SEED_DEMO_SHOES   (default 30)
    SIDE_BET_SEED_RNG_SEED     (default 20240101)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from app.config import get_settings
from app.db import close_client, ensure_indexes, get_db
from app.services import baccarat_dealer as bd
from app.services.side_bet_features import (
    FEATURE_NAMES,
    WindowRound,
    compute_corpus_stats,
    extract_raw_features,
    zscore,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_FACE_RANKS = {"10", "J", "Q", "K"}

DEMO_DATASET = "demo"
MONTE_CARLO_DATASET = "monte_carlo"

DEFAULT_MC_SHOE_COUNT = 2000
DEFAULT_DEMO_SHOE_COUNT = 30
DEFAULT_SEED = 20240101
# Demo shoes use a disjoint seed range so they can never coincide with a
# Monte Carlo shoe's shuffle, even though both datasets are kept in
# separate `datasetType` partitions regardless.
DEMO_SEED_OFFSET = 9_000_000


def _face_card_count(cards: list[dict]) -> int:
    return sum(1 for c in cards if c["rank"] in _FACE_RANKS)


def _hand_to_window_round(hand: bd.HandResult) -> WindowRound:
    return WindowRound(
        result=hand.result,
        margin=hand.margin,
        totalCardCount=hand.totalCardCount,
        bankerPair=hand.bankerPair,
        playerPair=hand.playerPair,
        faceCardCount=(
            sum(1 for c in hand.bankerCards if c.rank in _FACE_RANKS)
            + sum(1 for c in hand.playerCards if c.rank in _FACE_RANKS)
        ),
    )


def _hand_to_raw_doc(hand: bd.HandResult) -> dict:
    return {
        "bankerCards": [c.to_dict() for c in hand.bankerCards],
        "playerCards": [c.to_dict() for c in hand.playerCards],
        "bankerTotal": hand.bankerTotal,
        "playerTotal": hand.playerTotal,
        "result": hand.result,
        "margin": hand.margin,
        "bankerCardCount": hand.bankerCardCount,
        "playerCardCount": hand.playerCardCount,
        "totalCardCount": hand.totalCardCount,
        "bankerPair": hand.bankerPair,
        "playerPair": hand.playerPair,
        "bankerPerfectPair": hand.bankerPerfectPair,
        "playerPerfectPair": hand.playerPerfectPair,
        "naturalType": hand.naturalType,
        "lucky6Result": hand.lucky6Result,
    }


def simulate_shoe_hands(seed: int) -> list[bd.HandResult]:
    """Deal an entire shoe (every hand up to its cut-card) with a dedicated
    shuffle seeded by `seed`, so a given corpus version is reproducible."""
    dealer = bd.DealerShoe.new(seed=seed)
    hands: list[bd.HandResult] = []
    while dealer.can_deal_hand():
        hands.append(dealer.deal_hand())
    return hands


def build_slices_for_shoe(
    shoe_id: str, hands: list[bd.HandResult], window_length: int
) -> list[dict]:
    """Slide a window of `window_length` consecutive hands across one
    shoe's hand sequence, each paired with the very next hand's Lucky 6
    label. Never crosses a shoe boundary (each shoe's hand list is already
    exactly one physical shoe, cut-card to cut-card)."""
    window_rounds = [_hand_to_window_round(h) for h in hands]
    n = len(hands)
    slices: list[dict] = []
    for start in range(0, n - window_length):
        window = window_rounds[start : start + window_length]
        label_hand = hands[start + window_length]
        raw = extract_raw_features(window, window_length)
        slices.append(
            {
                "shoeId": shoe_id,
                "windowStartRoundNo": start + 1,
                "windowLength": window_length,
                "rawFeatures": raw,
                "nextLucky6Result": label_hand.lucky6Result,
            }
        )
    return slices


def _baseline_from_slices(slices: list[dict]) -> dict:
    total = len(slices)
    two_card_hits = sum(1 for s in slices if s["nextLucky6Result"] == "banker_6_two_cards")
    three_card_hits = sum(1 for s in slices if s["nextLucky6Result"] == "banker_6_three_cards")
    return {
        "sampleSize": total,
        "lucky6TwoCardHits": two_card_hits,
        "lucky6TwoCardRate": (two_card_hits / total) if total else 0.0,
        "lucky6ThreeCardHits": three_card_hits,
        "lucky6ThreeCardRate": (three_card_hits / total) if total else 0.0,
    }


async def _replace_version_docs(db, collection_name: str, match: dict, docs: list[dict]) -> None:
    collection = db[collection_name]
    await collection.delete_many(match)
    if not docs:
        return
    batch_size = 2000
    for i in range(0, len(docs), batch_size):
        await collection.insert_many(docs[i : i + batch_size])


async def seed_monte_carlo(
    shoe_count: int, base_seed: int, supported_windows: list[int], corpus_version: str, feature_version: str
) -> dict[int, list[dict]]:
    db = get_db()
    logger.info("Simulating %d Monte Carlo shoes (base_seed=%s)...", shoe_count, base_seed)

    raw_shoe_docs = []
    hands_by_shoe: dict[str, list[bd.HandResult]] = {}
    for i in range(shoe_count):
        shoe_id = f"mc_shoe_{i:05d}"
        seed = base_seed + i
        hands = simulate_shoe_hands(seed)
        hands_by_shoe[shoe_id] = hands
        raw_shoe_docs.append(
            {
                "shoeId": shoe_id,
                "datasetType": MONTE_CARLO_DATASET,
                "corpusVersion": corpus_version,
                "seed": seed,
                "handCount": len(hands),
                "hands": [_hand_to_raw_doc(h) for h in hands],
                "createdAt": datetime.now(timezone.utc),
            }
        )

    total_hands = sum(len(h) for h in hands_by_shoe.values())
    logger.info(
        "Dealt %d Monte Carlo shoes, %d total hands (avg %.1f hands/shoe).",
        shoe_count,
        total_hands,
        total_hands / shoe_count if shoe_count else 0.0,
    )

    await _replace_version_docs(
        db,
        "side_bet_raw_shoes",
        {"datasetType": MONTE_CARLO_DATASET, "corpusVersion": corpus_version},
        raw_shoe_docs,
    )

    slices_by_window: dict[int, list[dict]] = {}
    for window_length in supported_windows:
        slices: list[dict] = []
        for shoe_id, hands in hands_by_shoe.items():
            slices.extend(build_slices_for_shoe(shoe_id, hands, window_length))
        slices_by_window[window_length] = slices
        logger.info("N=%d: built %d Monte Carlo slices.", window_length, len(slices))

    return slices_by_window


async def seed_demo(
    demo_shoe_count: int, base_seed: int, supported_windows: list[int], corpus_version: str
) -> dict[int, list[dict]]:
    db = get_db()
    logger.info("Simulating %d demo shoes (base_seed=%s)...", demo_shoe_count, base_seed)

    raw_shoe_docs = []
    hands_by_shoe: dict[str, list[bd.HandResult]] = {}
    for i in range(demo_shoe_count):
        shoe_id = f"demo_shoe_{i:04d}"
        seed = base_seed + i
        hands = simulate_shoe_hands(seed)
        hands_by_shoe[shoe_id] = hands
        raw_shoe_docs.append(
            {
                "shoeId": shoe_id,
                "datasetType": DEMO_DATASET,
                "corpusVersion": corpus_version,
                "seed": seed,
                "handCount": len(hands),
                "hands": [_hand_to_raw_doc(h) for h in hands],
                "createdAt": datetime.now(timezone.utc),
            }
        )

    await _replace_version_docs(
        db,
        "side_bet_raw_shoes",
        {"datasetType": DEMO_DATASET, "corpusVersion": corpus_version},
        raw_shoe_docs,
    )

    slices_by_window: dict[int, list[dict]] = {}
    for window_length in supported_windows:
        slices: list[dict] = []
        for shoe_id, hands in hands_by_shoe.items():
            slices.extend(build_slices_for_shoe(shoe_id, hands, window_length))
        slices_by_window[window_length] = slices
        logger.info("N=%d: built %d demo slices.", window_length, len(slices))

    return slices_by_window


async def write_slices_stats_and_baselines(
    mc_slices_by_window: dict[int, list[dict]],
    demo_slices_by_window: dict[int, list[dict]],
    corpus_version: str,
    feature_version: str,
) -> None:
    db = get_db()
    now = datetime.now(timezone.utc)

    for window_length, mc_slices in mc_slices_by_window.items():
        if not mc_slices:
            logger.warning("N=%d: no Monte Carlo slices produced, skipping.", window_length)
            continue

        mean, std = compute_corpus_stats([s["rawFeatures"] for s in mc_slices])

        stats_doc = {
            "windowLength": window_length,
            "featureVersion": feature_version,
            "corpusVersion": corpus_version,
            "mean": mean,
            "std": std,
            "sampleSize": len(mc_slices),
            "featureNames": FEATURE_NAMES,
            "updatedAt": now,
        }
        await db.side_bet_stats.delete_many(
            {"windowLength": window_length, "featureVersion": feature_version, "corpusVersion": corpus_version}
        )
        await db.side_bet_stats.insert_one(stats_doc)

        mc_baseline = _baseline_from_slices(mc_slices)
        await db.side_bet_baselines.delete_many(
            {"windowLength": window_length, "datasetType": MONTE_CARLO_DATASET, "corpusVersion": corpus_version}
        )
        await db.side_bet_baselines.insert_one(
            {
                "windowLength": window_length,
                "datasetType": MONTE_CARLO_DATASET,
                "corpusVersion": corpus_version,
                "featureVersion": feature_version,
                "updatedAt": now,
                **mc_baseline,
            }
        )

        mc_docs = []
        for s in mc_slices:
            vector = zscore(s["rawFeatures"], mean, std)
            mc_docs.append(
                {
                    **s,
                    "datasetType": MONTE_CARLO_DATASET,
                    "corpusVersion": corpus_version,
                    "featureVersion": feature_version,
                    "vector": vector,
                    "createdAt": now,
                }
            )
        await _replace_version_docs(
            db,
            "side_bet_slices",
            {"windowLength": window_length, "datasetType": MONTE_CARLO_DATASET, "corpusVersion": corpus_version},
            mc_docs,
        )
        logger.info(
            "N=%d monte_carlo: %d slices written. baseline two=%.4f%% (%d/%d) three=%.4f%% (%d/%d)",
            window_length,
            len(mc_docs),
            mc_baseline["lucky6TwoCardRate"] * 100,
            mc_baseline["lucky6TwoCardHits"],
            mc_baseline["sampleSize"],
            mc_baseline["lucky6ThreeCardRate"] * 100,
            mc_baseline["lucky6ThreeCardHits"],
            mc_baseline["sampleSize"],
        )

        demo_slices = demo_slices_by_window.get(window_length, [])
        if not demo_slices:
            continue

        demo_baseline = _baseline_from_slices(demo_slices)
        await db.side_bet_baselines.delete_many(
            {"windowLength": window_length, "datasetType": DEMO_DATASET, "corpusVersion": corpus_version}
        )
        await db.side_bet_baselines.insert_one(
            {
                "windowLength": window_length,
                "datasetType": DEMO_DATASET,
                "corpusVersion": corpus_version,
                "featureVersion": feature_version,
                "updatedAt": now,
                **demo_baseline,
            }
        )

        demo_docs = []
        for s in demo_slices:
            # Demo slices always use the Monte-Carlo-fitted scaler for this
            # N (same coordinate system), but stay in their own dataset
            # partition and never contribute to the Monte Carlo baseline.
            vector = zscore(s["rawFeatures"], mean, std)
            demo_docs.append(
                {
                    **s,
                    "datasetType": DEMO_DATASET,
                    "corpusVersion": corpus_version,
                    "featureVersion": feature_version,
                    "vector": vector,
                    "createdAt": now,
                }
            )
        await _replace_version_docs(
            db,
            "side_bet_slices",
            {"windowLength": window_length, "datasetType": DEMO_DATASET, "corpusVersion": corpus_version},
            demo_docs,
        )
        logger.info(
            "N=%d demo: %d slices written. demo baseline two=%.4f%% (%d/%d) three=%.4f%% (%d/%d)",
            window_length,
            len(demo_docs),
            demo_baseline["lucky6TwoCardRate"] * 100,
            demo_baseline["lucky6TwoCardHits"],
            demo_baseline["sampleSize"],
            demo_baseline["lucky6ThreeCardRate"] * 100,
            demo_baseline["lucky6ThreeCardHits"],
            demo_baseline["sampleSize"],
        )


async def main() -> None:
    settings = get_settings()
    settings.validate_side_bet_window()
    supported_windows = settings.side_bet_supported_window_list
    corpus_version = settings.side_bet_corpus_version
    feature_version = settings.side_bet_feature_version

    mc_shoe_count = int(os.environ.get("SIDE_BET_SEED_SHOE_COUNT", DEFAULT_MC_SHOE_COUNT))
    demo_shoe_count = int(os.environ.get("SIDE_BET_SEED_DEMO_SHOES", DEFAULT_DEMO_SHOE_COUNT))
    base_seed = int(os.environ.get("SIDE_BET_SEED_RNG_SEED", DEFAULT_SEED))

    logger.info(
        "Seeding Side Bet corpus: windows=%s corpusVersion=%s featureVersion=%s mcShoes=%d demoShoes=%d seed=%d",
        supported_windows,
        corpus_version,
        feature_version,
        mc_shoe_count,
        demo_shoe_count,
        base_seed,
    )

    logger.info("Ensuring indexes (including 13-dim side_bet_vec_idx)...")
    await ensure_indexes()

    mc_slices_by_window = await seed_monte_carlo(
        mc_shoe_count, base_seed, supported_windows, corpus_version, feature_version
    )
    demo_slices_by_window = await seed_demo(
        demo_shoe_count, base_seed + DEMO_SEED_OFFSET, supported_windows, corpus_version
    )
    await write_slices_stats_and_baselines(
        mc_slices_by_window, demo_slices_by_window, corpus_version, feature_version
    )

    logger.info("Side Bet seed complete.")
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
