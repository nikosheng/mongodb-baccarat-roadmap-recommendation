"""Unit tests for side_bet_engine, using mocked Mongo (same approach as
test_derived_match_engine.py / test_match_engine.py — no real Atlas
connection needed)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import side_bet_engine


def _round_doc(round_no: int, result: str, source: str = "random_sim", **overrides) -> dict:
    doc = {
        "shoeId": "shoe1",
        "roundNo": round_no,
        "result": result,
        "source": source,
        "margin": 1 if result == "B" else (-1 if result == "P" else 0),
        "totalCardCount": 4,
        "bankerCardCount": 2,
        "playerCardCount": 2,
        "bankerPair": False,
        "playerPair": False,
        "bankerCards": [{"rank": "5", "suit": "S"}, {"rank": "4", "suit": "H"}],
        "playerCards": [{"rank": "6", "suit": "S"}, {"rank": "2", "suit": "H"}],
    }
    doc.update(overrides)
    return doc


def _make_fake_cursor(docs: list[dict]):
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=docs)
    return cursor


@pytest.mark.asyncio
async def test_insufficient_data_when_too_few_rounds():
    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor([_round_doc(1, "B")])
    fake_db.side_bet_matches.insert_one = AsyncMock()

    with patch.object(side_bet_engine, "get_db", return_value=fake_db):
        result = await side_bet_engine.compute_side_bet_match("shoe1", 1)

    assert result.insufficientData is True
    assert result.predictionForRoundNo == 2
    fake_db.side_bet_matches.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_insufficient_data_when_window_contains_manual_round():
    docs = [_round_doc(i, "B") for i in range(1, 11)]
    docs[3]["source"] = "manual_sim"
    docs[3]["bankerCards"] = None
    docs[3]["playerCards"] = None

    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor(list(reversed(docs)))
    fake_db.side_bet_matches.insert_one = AsyncMock()

    with (
        patch.object(side_bet_engine, "get_db", return_value=fake_db),
        patch("app.services.side_bet_engine.get_settings") as mock_settings,
    ):
        mock_settings.return_value = MagicMock(
            side_bet_window=10,
            side_bet_dataset="demo",
            side_bet_corpus_version="v1",
            side_bet_feature_version="sidebet-v1",
            side_bet_top_k=10,
            side_bet_candidate_multiplier=20,
            side_bet_min_samples_for_lift=3,
            validate_side_bet_window=MagicMock(),
        )
        result = await side_bet_engine.compute_side_bet_match("shoe1", 10)

    assert result.insufficientData is True


@pytest.mark.asyncio
async def test_insufficient_data_when_no_stats_or_baseline_seeded():
    docs = list(reversed([_round_doc(i, "B") for i in range(1, 11)]))
    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor(docs)
    fake_db.side_bet_stats.find_one = AsyncMock(return_value=None)
    fake_db.side_bet_baselines.find_one = AsyncMock(return_value=None)
    fake_db.side_bet_matches.insert_one = AsyncMock()

    with patch.object(side_bet_engine, "get_db", return_value=fake_db):
        result = await side_bet_engine.compute_side_bet_match("shoe1", 10)

    assert result.insufficientData is True
    assert "seed" in result.reason.lower() or "seed" in (result.reason or "")


def _mean_std_all_zero_one():
    from app.services.side_bet_features import FEATURE_NAMES

    mean = {name: 0.0 for name in FEATURE_NAMES}
    std = {name: 1.0 for name in FEATURE_NAMES}
    return mean, std


@pytest.mark.asyncio
async def test_full_pipeline_computes_rates_lift_and_dedupes_by_shoe():
    docs = list(reversed([_round_doc(i, "B") for i in range(1, 11)]))
    mean, std = _mean_std_all_zero_one()

    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor(docs)
    fake_db.side_bet_stats.find_one = AsyncMock(
        return_value={"mean": mean, "std": std}
    )
    fake_db.side_bet_baselines.find_one = AsyncMock(
        return_value={"lucky6TwoCardRate": 0.02, "lucky6ThreeCardRate": 0.01}
    )
    fake_db.side_bet_matches.insert_one = AsyncMock()

    # Raw vectorSearch hits: 12 candidates across only 10 distinct shoes
    # (two shoes appear twice, simulating overlapping windows), ordered by
    # score descending as Atlas would return them.
    raw_hits = [
        {"_id": "s1a", "shoeId": "shoeA", "nextLucky6Result": "banker_6_two_cards", "score": 0.95},
        {"_id": "s1b", "shoeId": "shoeA", "nextLucky6Result": "none", "score": 0.94},  # dup shoe, dropped
        {"_id": "s2", "shoeId": "shoeB", "nextLucky6Result": "banker_6_two_cards", "score": 0.93},
        {"_id": "s3", "shoeId": "shoeC", "nextLucky6Result": "banker_6_three_cards", "score": 0.90},
        {"_id": "s4", "shoeId": "shoeD", "nextLucky6Result": "none", "score": 0.88},
        {"_id": "s5", "shoeId": "shoeE", "nextLucky6Result": "none", "score": 0.87},
        {"_id": "s6", "shoeId": "shoeF", "nextLucky6Result": "none", "score": 0.85},
        {"_id": "s7", "shoeId": "shoeG", "nextLucky6Result": "none", "score": 0.83},
        {"_id": "s8", "shoeId": "shoeH", "nextLucky6Result": "none", "score": 0.80},
        {"_id": "s9", "shoeId": "shoeI", "nextLucky6Result": "none", "score": 0.78},
        {"_id": "s10", "shoeId": "shoeJ", "nextLucky6Result": "none", "score": 0.76},
    ]
    fake_db.side_bet_slices.aggregate.return_value.to_list = AsyncMock(return_value=raw_hits)

    with patch.object(side_bet_engine, "get_db", return_value=fake_db):
        result = await side_bet_engine.compute_side_bet_match("shoe1", 10)

    assert result.insufficientData is False
    assert result.neighborCount == 10  # deduped: shoeA kept once
    assert result.topSimilarityScore == 0.95
    assert result.lucky6TwoCardHits == 2
    assert result.lucky6TwoCardRate == pytest.approx(0.2)
    assert result.lucky6TwoCardBaseline == pytest.approx(0.02)
    assert result.lucky6TwoCardLift == pytest.approx(10.0)
    assert result.lucky6ThreeCardHits == 1
    assert result.lucky6ThreeCardRate == pytest.approx(0.1)
    assert result.lucky6ThreeCardLift == pytest.approx(10.0)
    assert result.predictionForRoundNo == 11
    fake_db.side_bet_matches.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_zero_baseline_does_not_produce_infinite_lift():
    docs = list(reversed([_round_doc(i, "B") for i in range(1, 11)]))
    mean, std = _mean_std_all_zero_one()

    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor(docs)
    fake_db.side_bet_stats.find_one = AsyncMock(return_value={"mean": mean, "std": std})
    fake_db.side_bet_baselines.find_one = AsyncMock(
        return_value={"lucky6TwoCardRate": 0.0, "lucky6ThreeCardRate": 0.0}
    )
    fake_db.side_bet_matches.insert_one = AsyncMock()
    fake_db.side_bet_slices.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {"_id": "s1", "shoeId": f"shoe{i}", "nextLucky6Result": "banker_6_two_cards", "score": 0.9}
            for i in range(10)
        ]
    )

    with patch.object(side_bet_engine, "get_db", return_value=fake_db):
        result = await side_bet_engine.compute_side_bet_match("shoe1", 10)

    assert result.lucky6TwoCardRate == pytest.approx(1.0)
    assert result.lucky6TwoCardLift is None


@pytest.mark.asyncio
async def test_insufficient_samples_suppresses_lift_but_keeps_rate():
    docs = list(reversed([_round_doc(i, "B") for i in range(1, 11)]))
    mean, std = _mean_std_all_zero_one()

    fake_db = MagicMock()
    fake_db.rounds.find.return_value = _make_fake_cursor(docs)
    fake_db.side_bet_stats.find_one = AsyncMock(return_value={"mean": mean, "std": std})
    fake_db.side_bet_baselines.find_one = AsyncMock(
        return_value={"lucky6TwoCardRate": 0.02, "lucky6ThreeCardRate": 0.01}
    )
    fake_db.side_bet_matches.insert_one = AsyncMock()
    # Only 2 distinct-shoe neighbors returned — below min_samples_for_lift (3).
    fake_db.side_bet_slices.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {"_id": "s1", "shoeId": "shoeA", "nextLucky6Result": "banker_6_two_cards", "score": 0.9},
            {"_id": "s2", "shoeId": "shoeB", "nextLucky6Result": "none", "score": 0.8},
        ]
    )

    with patch.object(side_bet_engine, "get_db", return_value=fake_db):
        result = await side_bet_engine.compute_side_bet_match("shoe1", 10)

    assert result.neighborCount == 2
    assert result.lucky6TwoCardRate == pytest.approx(0.5)
    assert result.lucky6TwoCardLift is None
    assert result.reason is not None
