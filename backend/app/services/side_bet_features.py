"""Single, reusable 13-dimensional Side Bet feature extractor (see
docs/side-bet-lucky6-plan.md §4). Both the Monte Carlo/demo seed script and
the live query engine must call `extract_raw_features` — never reimplement
the encoding separately — so corpus vectors and live query vectors are
always built from identical logic.

Every raw feature is computed over a window of exactly `N` *consecutive,
same-shoe, card-complete* rounds, plus the single round immediately
following the window (used only to derive the next-hand Lucky 6 label, not
as part of the feature window itself). Manual B/P/T rounds (no card face)
must never be included in a window — callers are responsible for only
passing windows built from `source="random_sim"` rounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence

Outcome = Literal["B", "P", "T"]

# Fixed feature order — this order IS the schema. Changing it, or adding/
# removing a feature, is a new `featureVersion` (see plan §5.1) and requires
# recomputing every corpus vector.
FEATURE_NAMES: list[str] = [
    "bankerWinRatio",
    "playerWinRatio",
    "tieRatio",
    "avgMargin",
    "marginVolatility",
    "ratio4Cards",
    "ratio5Cards",
    "ratio6Cards",
    "faceCardDensity",
    "roundsSinceLastTie",
    "roundsSinceLastPair",
    "currentStreakSigned",
    "chopRatio",
]

FEATURE_VERSION = "sidebet-v1"
VECTOR_DIM = len(FEATURE_NAMES)


@dataclass
class WindowRound:
    """Minimal shape side_bet_features needs from a Round document — keeps
    this module decoupled from the Mongo document / Pydantic schema."""

    result: Outcome
    margin: int
    totalCardCount: int
    bankerPair: bool
    playerPair: bool
    # Number of 10/J/Q/K-valued cards actually dealt this hand (used for
    # faceCardDensity); pass in whatever rank-counting the caller already has.
    faceCardCount: int


class InsufficientWindowError(ValueError):
    """Raised when the given rounds cannot form a complete, card-backed
    N-round feature window (wrong length, includes a manual round, etc.).
    Callers must surface this as `insufficientData`, never silently pad or
    guess values."""


def extract_raw_features(window: Sequence[WindowRound], window_length: int) -> dict[str, float]:
    """Compute the 13 raw (pre z-score) features for `window`, which must
    contain exactly `window_length` consecutive, card-complete rounds from a
    single shoe, oldest-first."""
    n = len(window)
    if n != window_length or n == 0:
        raise InsufficientWindowError(
            f"expected exactly {window_length} rounds, got {n}"
        )

    results = [r.result for r in window]
    margins = [r.margin for r in window]

    banker_wins = results.count("B")
    player_wins = results.count("P")
    ties = results.count("T")

    banker_win_ratio = banker_wins / n
    player_win_ratio = player_wins / n
    tie_ratio = ties / n

    avg_margin = sum(margins) / n
    margin_volatility = _population_std(margins, avg_margin)

    card_counts = [r.totalCardCount for r in window]
    ratio4 = card_counts.count(4) / n
    ratio5 = card_counts.count(5) / n
    ratio6 = card_counts.count(6) / n

    total_cards_dealt = sum(card_counts)
    total_face_cards = sum(r.faceCardCount for r in window)
    face_card_density = (total_face_cards / total_cards_dealt) if total_cards_dealt > 0 else 0.0

    rounds_since_last_tie = _rounds_since(results, lambda r: r == "T", n)
    rounds_since_last_pair = _rounds_since(
        [r.bankerPair or r.playerPair for r in window], lambda v: v, n
    )

    current_streak_signed = _current_streak_signed(results)
    chop_ratio = _chop_ratio(results)

    return {
        "bankerWinRatio": banker_win_ratio,
        "playerWinRatio": player_win_ratio,
        "tieRatio": tie_ratio,
        "avgMargin": avg_margin,
        "marginVolatility": margin_volatility,
        "ratio4Cards": ratio4,
        "ratio5Cards": ratio5,
        "ratio6Cards": ratio6,
        "faceCardDensity": face_card_density,
        "roundsSinceLastTie": float(rounds_since_last_tie),
        "roundsSinceLastPair": float(rounds_since_last_pair),
        "currentStreakSigned": float(current_streak_signed),
        "chopRatio": chop_ratio,
    }


def _population_std(values: Sequence[float], mean: float) -> float:
    if not values:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _rounds_since(items: Sequence, predicate, n: int) -> int:
    """Distance from the window's tail back to the most recent item
    satisfying `predicate`, counted as "how many rounds have happened
    since" (0 = the event was the very last round in the window; 1 = one
    round has happened since, etc.). If none found in the window, returns
    `n` (the plan's truncate-to-N convention). Matches the worked example in
    docs/side-bet-lucky6-plan.md §12.1: a pair at the window's second-to-
    last round (Round 9 of 10) gives roundsSinceLastPair=1."""
    for i in range(n - 1, -1, -1):
        if predicate(items[i]):
            return (n - 1) - i
    return n


def _current_streak_signed(results: Sequence[Outcome]) -> int:
    """Length of the trailing run of identical non-Tie results at the tail
    of the window, positive for Banker, negative for Player. A Tie at the
    very tail does not extend or reset the Big-Road streak by itself — we
    look through trailing Ties to the last B/P run, matching how Big Road
    treats Ties (a marker on the existing column, not a new column)."""
    last_bp: Outcome | None = None
    streak = 0
    for r in reversed(results):
        if r == "T":
            continue
        if last_bp is None:
            last_bp = r
            streak = 1
        elif r == last_bp:
            streak += 1
        else:
            break
    if last_bp is None:
        return 0
    return streak if last_bp == "B" else -streak


def _chop_ratio(results: Sequence[Outcome]) -> float:
    """Fraction of adjacent non-Tie result pairs that differ (B->P or
    P->B). Ties are excluded entirely from the comparison sequence since
    they aren't a Big-Road column transition."""
    bp_only = [r for r in results if r != "T"]
    if len(bp_only) < 2:
        return 0.0
    comparable_pairs = len(bp_only) - 1
    transitions = sum(1 for a, b in zip(bp_only, bp_only[1:]) if a != b)
    return transitions / comparable_pairs


def zscore(raw_features: dict[str, float], mean: dict[str, float], std: dict[str, float]) -> list[float]:
    """Apply the corpus-fixed mean/std to raw features, producing the fixed-
    order 13-float vector. `std[j] == 0` is handled by setting that
    dimension's z-score to 0 rather than dividing by zero."""
    vector: list[float] = []
    for name in FEATURE_NAMES:
        raw = raw_features[name]
        m = mean[name]
        s = std[name]
        vector.append(0.0 if s == 0 else (raw - m) / s)
    return vector


def compute_corpus_stats(all_raw_features: Sequence[dict[str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute per-dimension mean/std over an entire corpus of raw feature
    dicts (same N/corpus version). Population std, matching marginVolatility's
    own convention and plan §5.1."""
    mean: dict[str, float] = {}
    std: dict[str, float] = {}
    count = len(all_raw_features)
    if count == 0:
        raise ValueError("cannot compute corpus stats over an empty corpus")
    for name in FEATURE_NAMES:
        values = [f[name] for f in all_raw_features]
        m = sum(values) / count
        mean[name] = m
        std[name] = _population_std(values, m)
    return mean, std
