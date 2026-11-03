"""
describe_window_in_nl — the single semantic bridge between raw B/P/T
sequences and the text that gets embedded by Voyage.

CRITICAL INVARIANT: both pattern-library seeding and runtime window
matching MUST call this exact function (same version) so that both
sides of the vector search live in the same semantic subspace.

Design principles (see project design doc):
  1. Expand symbols to full English words (Banker/Player/Tie) — richer
     token vocabulary than single letters.
  2. Never emit raw numbers (ratios, counts) into the text. Numbers are
     computed internally then translated into natural-language buckets.
     Embedding models handle semantic words far better than digit
     tokens, which carry little magnitude information.
  3. Fixed 9-line bullet template — stable phrasing keeps embeddings
     aligned across many different sequences, so only the meaningful
     semantic differences move the vector.
"""

from __future__ import annotations

from dataclasses import dataclass

NL_DESCRIBER_VERSION = "1.0.0"

VALID_SYMBOLS = {"B", "P", "T"}
WORD = {"B": "Banker", "P": "Player", "T": "Tie"}


class InvalidSequenceError(ValueError):
    pass


@dataclass
class WindowStats:
    length: int
    counts: dict[str, int]
    ratios: dict[str, float]
    max_streak: dict[str, int]
    current_streak_type: str
    current_streak_len: int
    chop_count: int
    chop_ratio: float
    double_chop_count: int
    last_three: list[str]
    reversal: str | None
    rhythm: str


# ---------------------------------------------------------------------------
# Stage 1+2: validation & statistics
# ---------------------------------------------------------------------------

def _validate(sequence: list[str]) -> None:
    if not sequence:
        raise InvalidSequenceError("sequence must not be empty")
    bad = [s for s in sequence if s not in VALID_SYMBOLS]
    if bad:
        raise InvalidSequenceError(f"invalid symbols in sequence: {bad}")


def _compute_stats(sequence: list[str]) -> WindowStats:
    n = len(sequence)
    counts = {k: sequence.count(k) for k in ("B", "P", "T")}
    ratios = {k: counts[k] / n for k in counts}

    # max streak per side (consecutive runs, ties break streaks for B/P purposes
    # but we still track T's own streak)
    max_streak = {"B": 0, "P": 0, "T": 0}
    run_type = None
    run_len = 0
    for s in sequence:
        if s == run_type:
            run_len += 1
        else:
            run_type = s
            run_len = 1
        max_streak[s] = max(max_streak[s], run_len)

    # current streak = run ending at the last element
    current_streak_type = sequence[-1]
    current_streak_len = 1
    for s in reversed(sequence[:-1]):
        if s == current_streak_type:
            current_streak_len += 1
        else:
            break

    # chop_count: adjacent B/P alternations (ignore Tie involvement in ratio calc)
    chop_count = 0
    transitions = 0
    for i in range(1, n):
        if sequence[i] in ("B", "P") and sequence[i - 1] in ("B", "P"):
            transitions += 1
            if sequence[i] != sequence[i - 1]:
                chop_count += 1
    chop_ratio = chop_count / transitions if transitions else 0.0

    # double_chop_count: count of "XX YY" repeating pair patterns (BBPP, PPBB...)
    double_chop_count = 0
    i = 0
    bp_only = [s for s in sequence if s in ("B", "P")]
    j = 0
    while j + 3 < len(bp_only):
        a, b, c, d = bp_only[j : j + 4]
        if a == b and c == d and a != c:
            double_chop_count += 1
            j += 2
        else:
            j += 1

    last_three = sequence[-3:]

    # reversal detection: was there a long streak (>=4) immediately followed
    # by a short interruption (1-2) before current tail?
    reversal = _detect_reversal(sequence, max_streak)

    rhythm = _detect_rhythm(double_chop_count, max_streak, chop_ratio)

    return WindowStats(
        length=n,
        counts=counts,
        ratios=ratios,
        max_streak=max_streak,
        current_streak_type=current_streak_type,
        current_streak_len=current_streak_len,
        chop_count=chop_count,
        chop_ratio=chop_ratio,
        double_chop_count=double_chop_count,
        last_three=last_three,
        reversal=reversal,
        rhythm=rhythm,
    )


def _runs(sequence: list[str]) -> list[tuple[str, int]]:
    """Collapse sequence into list of (symbol, run_length)."""
    out: list[tuple[str, int]] = []
    for s in sequence:
        if out and out[-1][0] == s:
            out[-1] = (s, out[-1][1] + 1)
        else:
            out.append((s, 1))
    return out


def _detect_reversal(sequence: list[str], max_streak: dict[str, int]) -> str | None:
    runs = _runs(sequence)

    # Pattern: [long streak X] [brief interruption Y] [resumed X]
    if len(runs) >= 3:
        r1_sym, r1_len = runs[-3]
        r2_sym, r2_len = runs[-2]
        r3_sym, r3_len = runs[-1]
        if (
            r1_sym in ("B", "P")
            and r1_len >= 4
            and r2_sym in ("B", "P")
            and r2_sym != r1_sym
            and r2_len <= 2
            and r3_sym == r1_sym
        ):
            return f"{WORD[r1_sym]} resumed shortly after a brief {WORD[r2_sym]} interruption"

    # Pattern: [long streak X] [brief interruption Y] (window ends right after break)
    if len(runs) >= 2:
        prev_sym, prev_len = runs[-2]
        last_sym, last_len = runs[-1]
        if (
            prev_sym in ("B", "P")
            and prev_len >= 4
            and last_sym in ("B", "P")
            and last_sym != prev_sym
            and last_len <= 2
        ):
            return f"a long {WORD[prev_sym]} streak just interrupted by a single {WORD[last_sym]}"

    return None


def _detect_rhythm(double_chop_count: int, max_streak: dict[str, int], chop_ratio: float) -> str:
    longest = max(max_streak["B"], max_streak["P"])
    if double_chop_count >= 2 and longest <= 2:
        return "repeating pair-wise rhythm (double-chop)"
    if chop_ratio >= 0.8:
        return "repeating alternating rhythm"
    if longest >= 5 and chop_ratio <= 0.2:
        return "strong one-sided trend"
    if longest >= 5:
        return "one-sided trend with sudden break"
    return "mixed rhythm with short runs"


# ---------------------------------------------------------------------------
# Stage 3: numeric -> language buckets
# ---------------------------------------------------------------------------

def _bucket_length(n: int) -> str:
    if n <= 4:
        return "very short window"
    if n <= 7:
        return "medium window"
    return "full window"


def _bucket_dominance(stats: WindowStats) -> str:
    if stats.ratios["T"] >= 0.5:
        return "Tie results dominate this window"
    b, p = stats.ratios["B"], stats.ratios["P"]
    if abs(b - p) < 0.05:
        return "balanced between Banker and Player"
    side, ratio = ("Banker", b) if b > p else ("Player", p)
    if ratio >= 0.75:
        return f"{side} heavily dominates"
    if ratio >= 0.60:
        return f"{side} strongly leads"
    if ratio >= 0.50:
        return f"{side} slightly ahead"
    return f"{side} slightly ahead"


def _bucket_current_state(stats: WindowStats) -> str:
    side = WORD[stats.current_streak_type]
    n = stats.current_streak_len
    if n == 1:
        return f"single {side} just appeared"
    if n == 2:
        return f"short {side} streak of two"
    if n <= 4:
        return f"ongoing {side} streak of {n}"
    return f"long ongoing {side} streak of {n}"


def _bucket_streak(n: int) -> str:
    labels = {
        0: "no streak",
        1: "no run (isolated)",
        2: "very short run of two",
        3: "short run of three",
        4: "medium run of four",
        5: "long run of five",
        6: "very long run of six",
    }
    if n in labels:
        return labels[n]
    return f"extreme run of {n}"


def _bucket_longest_run(stats: WindowStats) -> str:
    b, p = stats.max_streak["B"], stats.max_streak["P"]
    if b == 0 and p == 0:
        return "no run (isolated)"
    if b >= p:
        return _bucket_streak(b)
    return _bucket_streak(p)


def _bucket_chop(stats: WindowStats) -> str:
    ratio = stats.chop_ratio
    if ratio >= 0.80:
        return "pure chopping rhythm with constant alternation"
    if ratio >= 0.60:
        return "frequent alternation"
    if ratio >= 0.40:
        return "moderate alternation"
    if ratio >= 0.20:
        return "occasional alternation"
    return "no clear alternation"


def _bucket_tie(ratio: float) -> str:
    if ratio == 0:
        return "no Tie in this window"
    if ratio <= 0.10:
        return "rare Tie activity"
    if ratio <= 0.20:
        return "occasional Tie activity"
    return "frequent Tie activity"


def _words(symbols: list[str]) -> str:
    return " ".join(WORD[s] for s in symbols)


# ---------------------------------------------------------------------------
# Stage 4: final template
# ---------------------------------------------------------------------------

def describe_window_in_nl(sequence: list[str]) -> str:
    """Translate a B/P/T sequence into a fixed-format English description
    used as the embedding input for both pattern library seeding and
    runtime window matching.

    Raises InvalidSequenceError on empty or malformed input.
    """
    _validate(sequence)
    stats = _compute_stats(sequence)

    lines = [
        f"Baccarat sequence: {_words(sequence)}",
        "",
        "Window summary:",
        f"- Length: {_bucket_length(stats.length)}",
        f"- Dominant side: {_bucket_dominance(stats)}",
        f"- Current state: {_bucket_current_state(stats)}",
        f"- Longest run: {_bucket_longest_run(stats)}",
        f"- Alternation: {_bucket_chop(stats)}",
        f"- Tie activity: {_bucket_tie(stats.ratios['T'])}",
        f"- Recent reversal: {stats.reversal or 'no notable reversal'}",
        f"- Overall rhythm: {stats.rhythm}",
        f"- Last three results: {_words(stats.last_three)}",
    ]
    return "\n".join(lines)


def compute_window_stats(sequence: list[str]) -> WindowStats:
    """Public accessor for stats, useful for debug endpoints."""
    _validate(sequence)
    return _compute_stats(sequence)
