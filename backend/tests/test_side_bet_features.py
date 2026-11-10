"""Unit tests for the 13-dim Side Bet feature encoder. Includes a
regression test reproducing the worked demo example from
docs/side-bet-lucky6-plan.md §12.1 exactly (raw features and z-scores)."""

from __future__ import annotations

import pytest

from app.services import side_bet_features as sbf
from app.services.side_bet_features import InsufficientWindowError, WindowRound

PLAN_DEMO_ROWS = [
    # result, margin, totalCardCount, bankerPair, playerPair, faceCardCount
    ("B", 3, 4, False, False, 1),
    ("P", -6, 5, True, False, 4),
    ("B", 1, 6, False, False, 1),
    ("B", 4, 4, False, False, 1),
    ("B", 5, 6, False, False, 0),
    ("B", 2, 6, False, False, 3),
    ("P", -3, 5, False, False, 1),
    ("B", 8, 4, False, False, 2),
    ("B", 3, 5, False, True, 2),
    ("B", 2, 6, False, False, 0),
]


def _plan_demo_window() -> list[WindowRound]:
    return [
        WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f)
        for r, m, t, bp, pp, f in PLAN_DEMO_ROWS
    ]


def test_feature_order_is_fixed_and_dim_is_13():
    assert len(sbf.FEATURE_NAMES) == 13
    assert sbf.VECTOR_DIM == 13
    assert sbf.FEATURE_NAMES[0] == "bankerWinRatio"
    assert sbf.FEATURE_NAMES[-1] == "chopRatio"


def test_plan_demo_raw_features_match_worked_example():
    feats = sbf.extract_raw_features(_plan_demo_window(), window_length=10)
    assert feats["bankerWinRatio"] == pytest.approx(0.80)
    assert feats["playerWinRatio"] == pytest.approx(0.20)
    assert feats["tieRatio"] == pytest.approx(0.0)
    assert feats["avgMargin"] == pytest.approx(1.90)
    assert feats["marginVolatility"] == pytest.approx(3.7537, abs=1e-3)
    assert feats["ratio4Cards"] == pytest.approx(0.30)
    assert feats["ratio5Cards"] == pytest.approx(0.30)
    assert feats["ratio6Cards"] == pytest.approx(0.40)
    assert feats["faceCardDensity"] == pytest.approx(15 / 51, abs=1e-4)
    assert feats["roundsSinceLastTie"] == 10.0
    assert feats["roundsSinceLastPair"] == 1.0
    assert feats["currentStreakSigned"] == 3.0
    assert feats["chopRatio"] == pytest.approx(4 / 9, abs=1e-4)


def test_card_ratios_sum_to_one():
    feats = sbf.extract_raw_features(_plan_demo_window(), window_length=10)
    total = feats["ratio4Cards"] + feats["ratio5Cards"] + feats["ratio6Cards"]
    assert total == pytest.approx(1.0)


def test_win_ratios_sum_to_one():
    feats = sbf.extract_raw_features(_plan_demo_window(), window_length=10)
    total = feats["bankerWinRatio"] + feats["playerWinRatio"] + feats["tieRatio"]
    assert total == pytest.approx(1.0)


def test_wrong_length_window_raises_insufficient():
    window = _plan_demo_window()[:5]
    with pytest.raises(InsufficientWindowError):
        sbf.extract_raw_features(window, window_length=10)


def test_empty_window_raises_insufficient():
    with pytest.raises(InsufficientWindowError):
        sbf.extract_raw_features([], window_length=10)


def test_current_streak_signed_player_and_ties_dont_reset_it():
    # Tail: B B P P P -> player streak of 3, negative sign.
    rows = [("B", 1, 4, False, False, 0)] * 2 + [("P", -1, 4, False, False, 0)] * 3
    window = [WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f) for r, m, t, bp, pp, f in rows]
    feats = sbf.extract_raw_features(window, window_length=5)
    assert feats["currentStreakSigned"] == -3.0

    # Trailing Tie should not reset/extend the B/P streak itself (Big Road
    # convention: a Tie marks the existing column, it doesn't start a new one).
    rows_with_tie = rows + [("T", 0, 4, False, False, 0)]
    window2 = [WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f) for r, m, t, bp, pp, f in rows_with_tie]
    feats2 = sbf.extract_raw_features(window2, window_length=6)
    assert feats2["currentStreakSigned"] == -3.0


def test_rounds_since_last_tie_zero_when_tie_is_tail_round():
    rows = [("B", 1, 4, False, False, 0)] * 4 + [("T", 0, 4, False, False, 0)]
    window = [WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f) for r, m, t, bp, pp, f in rows]
    feats = sbf.extract_raw_features(window, window_length=5)
    assert feats["roundsSinceLastTie"] == 0.0


def test_chop_ratio_all_chop_vs_all_streak():
    chop_rows = [("B", 1, 4, False, False, 0), ("P", -1, 4, False, False, 0)] * 2
    chop_window = [WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f) for r, m, t, bp, pp, f in chop_rows]
    assert sbf.extract_raw_features(chop_window, window_length=4)["chopRatio"] == pytest.approx(1.0)

    streak_rows = [("B", 1, 4, False, False, 0)] * 4
    streak_window = [WindowRound(result=r, margin=m, totalCardCount=t, bankerPair=bp, playerPair=pp, faceCardCount=f) for r, m, t, bp, pp, f in streak_rows]
    assert sbf.extract_raw_features(streak_window, window_length=4)["chopRatio"] == pytest.approx(0.0)


def test_zscore_matches_plan_example_for_first_four_dims():
    feats = sbf.extract_raw_features(_plan_demo_window(), window_length=10)
    mean = {name: 0.0 for name in sbf.FEATURE_NAMES}
    std = {name: 1.0 for name in sbf.FEATURE_NAMES}
    mean.update({"bankerWinRatio": 0.459, "playerWinRatio": 0.446, "tieRatio": 0.095, "avgMargin": 0.000})
    std.update({"bankerWinRatio": 0.158, "playerWinRatio": 0.157, "tieRatio": 0.093, "avgMargin": 2.800})

    vector = sbf.zscore(feats, mean, std)
    assert len(vector) == 13
    assert vector[0] == pytest.approx(2.158, abs=1e-3)
    assert vector[1] == pytest.approx(-1.567, abs=1e-3)
    assert vector[2] == pytest.approx(-1.022, abs=1e-3)
    assert vector[3] == pytest.approx(0.679, abs=1e-3)


def test_zscore_zero_std_dimension_is_set_to_zero_not_divided():
    feats = {name: 1.0 for name in sbf.FEATURE_NAMES}
    mean = {name: 0.0 for name in sbf.FEATURE_NAMES}
    std = {name: 0.0 for name in sbf.FEATURE_NAMES}
    vector = sbf.zscore(feats, mean, std)
    assert vector == [0.0] * 13


def test_compute_corpus_stats_matches_simple_mean_std():
    data = [
        {name: float(i) for name in sbf.FEATURE_NAMES}
        for i in range(5)
    ]
    mean, std = sbf.compute_corpus_stats(data)
    assert mean["bankerWinRatio"] == pytest.approx(2.0)
    assert std["bankerWinRatio"] == pytest.approx(1.4142, abs=1e-3)


def test_compute_corpus_stats_rejects_empty_corpus():
    with pytest.raises(ValueError):
        sbf.compute_corpus_stats([])
