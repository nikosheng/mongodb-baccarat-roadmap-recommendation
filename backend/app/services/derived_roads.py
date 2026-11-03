"""Big Road + derived "下三路" (Big Eye Boy / Small Road / Cockroach Pig)
computation, and the NL description bridge for the second vector search.

CRITICAL INVARIANT #1: `compute_big_road` / `compute_derived_road` must stay
behaviorally identical to the TypeScript implementation in
`frontend/src/lib/roads.ts`. Both are exercised against the same fixture
file (`backend/tests/fixtures/road_cases.json`) — the frontend renders
roads instantly from local round state while the backend recomputes the
same roads to build the NL text used for vector search, and if the two
disagree the displayed grids and the recommendation panel will look
inconsistent to the user.

CRITICAL INVARIANT #2 (mirrors window_text.py): both derived-pattern seeding
and runtime matching MUST call `describe_derived_in_nl` (same version) so
both sides of the second vector search live in the same semantic subspace.

Big Road layout rules (standard casino "Big Road"):
  - Same outcome as previous -> extends downward in the same column.
  - Different outcome -> opens a new column, starting at row 0.
  - When a streak reaches the bottom row (row = ROWS-1) and continues, it
    "tails": each subsequent same-outcome result moves one column to the
    right while staying pinned to the bottom row, until the streak breaks.
  - Tie does not open a new column or break a streak; it's recorded as a
    counter on the most recently placed cell. Ties before the first B/P
    result attach to that first result; a tie-only shoe uses a placeholder.

Derived road rule (generalized by `offset`: 1 = Big Eye Boy, 2 = Small Road,
3 = Cockroach Pig). For each newly placed Big Road B/P cell at (col, row):
  - If row > 0 (continuing a column): compare whether column (col - offset)
    has a cell at this same row index. If yes -> Red, else -> Blue.
  - If row == 0 (a brand new column): compare the total height of column
    (col - offset) vs column (col - offset - 1). Equal -> Red, different ->
    Blue.
  - Not enough history yet (referenced column index < 0) -> no symbol yet.
The resulting R/B symbol sequence is then laid out on its own road using the
same down-then-tail algorithm as the Big Road.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeVar

Outcome = Literal["B", "P", "T"]
RoadColor = Literal["R", "B"]

ROAD_ROWS = 6
NL_DERIVED_VERSION = "3.0.0"

T = TypeVar("T")


@dataclass
class BigRoadCell:
    col: int
    row: int
    symbol: str  # "B" | "P" | "T" (T only when a shoe has no B/P result)
    tieCount: int = 0


@dataclass
class DerivedCell:
    col: int
    row: int
    color: RoadColor


@dataclass
class DerivedTailSymbols:
    bigEye: str = ""
    small: str = ""
    cockroach: str = ""


@dataclass
class AllRoads:
    bigRoad: list[BigRoadCell] = field(default_factory=list)
    bigEye: list[DerivedCell] = field(default_factory=list)
    small: list[DerivedCell] = field(default_factory=list)
    cockroach: list[DerivedCell] = field(default_factory=list)


class InvalidRoadsError(ValueError):
    pass


def _layout_run_sequence(symbols: list[str]) -> list[tuple[int, int, str]]:
    """Generic down-then-tail layout for a sequence of same/different
    symbols. Returns list of (col, row, symbol)."""
    out: list[tuple[int, int, str]] = []
    col = 0
    row = 0
    last: str | None = None
    tailing = False

    for s in symbols:
        if last is None:
            col = 0
            row = 0
        elif s == last:
            if tailing:
                col += 1
            elif row + 1 < ROAD_ROWS:
                row += 1
            else:
                tailing = True
                col += 1
                row = ROAD_ROWS - 1
        else:
            col += 1
            row = 0
            tailing = False
        last = s
        out.append((col, row, s))

    return out


def compute_big_road(results: list[str]) -> list[BigRoadCell]:
    """Compute the Big Road cell layout from a raw B/P/T result sequence.

    Ties before the first B/P are attached to that first B/P cell. If the
    sequence contains only ties, retain a tie-only placeholder at (0, 0).
    """
    bp_symbols: list[str] = []
    tie_counts_after_index: dict[int, int] = {}
    pending_leading_ties = 0

    for r in results:
        if r == "T":
            if not bp_symbols:
                pending_leading_ties += 1
            else:
                idx = len(bp_symbols) - 1
                tie_counts_after_index[idx] = tie_counts_after_index.get(idx, 0) + 1
            continue
        bp_symbols.append(r)

    cells: list[BigRoadCell] = []
    if pending_leading_ties > 0:
        if bp_symbols:
            # A leading tie has no previous B/P cell to mark. Carry it onto
            # the first resolved outcome so its tie slash shares that cell.
            tie_counts_after_index[0] = (
                tie_counts_after_index.get(0, 0) + pending_leading_ties
            )
        else:
            # A shoe containing only ties still needs a visible placeholder.
            cells.append(
                BigRoadCell(
                    col=0, row=0, symbol="T", tieCount=pending_leading_ties
                )
            )

    for i, (col, row, symbol) in enumerate(_layout_run_sequence(bp_symbols)):
        cells.append(
            BigRoadCell(
                col=col,
                row=row,
                symbol=symbol,
                tieCount=tie_counts_after_index.get(i, 0),
            )
        )

    return cells


def compute_derived_road(big_road_cells: list[BigRoadCell], offset: int) -> list[DerivedCell]:
    """Derive one of the three 下三路 (offset=1 Big Eye Boy, 2 Small Road,
    3 Cockroach Pig) from the Big Road's B/P cells."""
    bp_cells = [c for c in big_road_cells if c.symbol in ("B", "P")]
    heights: dict[int, int] = {}
    occupied: set[tuple[int, int]] = set()
    symbols: list[str] = []

    for cell in bp_cells:
        heights[cell.col] = heights.get(cell.col, 0) + 1
        occupied.add((cell.col, cell.row))
        col, row = cell.col, cell.row
        left1 = col - offset
        left2 = col - offset - 1

        if left1 < 0:
            continue

        if row > 0:
            exists = (left1, row) in occupied
            symbols.append("R" if exists else "B")
        else:
            if left2 < 0:
                continue
            h1 = heights.get(left1, 0)
            h2 = heights.get(left2, 0)
            symbols.append("R" if h1 == h2 else "B")

    return [DerivedCell(col=c, row=r, color=s) for c, r, s in _layout_run_sequence(symbols)]


def compute_all_roads(results: list[str]) -> AllRoads:
    big_road = compute_big_road(results)
    return AllRoads(
        bigRoad=big_road,
        bigEye=compute_derived_road(big_road, 1),
        small=compute_derived_road(big_road, 2),
        cockroach=compute_derived_road(big_road, 3),
    )


def tail_symbols(cells: list[DerivedCell], k: int = 12) -> str:
    """Extract the most recent K R/B symbols from a derived road, in
    chronological order."""
    return "".join(c.color for c in cells[-k:])


def extract_tail_symbols(roads: AllRoads, k: int = 12) -> DerivedTailSymbols:
    return DerivedTailSymbols(
        bigEye=tail_symbols(roads.bigEye, k),
        small=tail_symbols(roads.small, k),
        cockroach=tail_symbols(roads.cockroach, k),
    )


def ask_next(results: list[str]) -> dict[str, DerivedTailSymbols]:
    """Simulate appending one more Banker or Player result and report what
    the three derived roads' tail symbols would look like in each case.

    Not wired up to any API endpoint yet (reserved for a future "問路"
    feature) — kept here so the core simulation logic lives alongside the
    rest of the derived-road computation.
    """
    out: dict[str, DerivedTailSymbols] = {}
    for hypothetical in ("B", "P"):
        roads = compute_all_roads([*results, hypothetical])
        out["ifBanker" if hypothetical == "B" else "ifPlayer"] = extract_tail_symbols(roads)
    return out


# ---------------------------------------------------------------------------
# NL description (version 3.0.0) — the embedding bridge for the second
# vector search.
#
# History of attempts, informed by app/seed/calibrate_derived.py:
#   v1.0.0: flat per-road bullet template, no archetype language.
#           -> pairwise cosine 0.93-0.9996 (collapsed cluster).
#   v2.0.0a: single archetype headline + per-road bullets.
#            -> improved to min 0.80, but a shared boilerplate opening
#               ("SIGNAL CLASSIFICATION: ... (X pattern)...") across every
#               archetype, plus per-road bullets with near-identical
#               phrasing, still pulled pairs together (up to 0.96).
#   v2.0.0b: multi-dimension present/absent bullets (mirroring
#            window_text.py's bucket style).
#            -> WORSE (min 0.92): because most patterns are a "pure"
#               instance of exactly one archetype, 4 of 5 dimension
#               bullets end up as near-identical "absent" boilerplate,
#               which swamps the one differing bullet. This only works in
#               window_text.py because every dimension there always
#               produces a *varying* value (dominance always picks a side,
#               streak always buckets to *something*) — there's no
#               permanent "N/A" filler diluting most of the text.
#   v3.0.0 (current): single archetype narrative, but with a COMPLETELY
#           different opening clause per archetype (no shared prefix like
#           "SIGNAL CLASSIFICATION:"), the templated per-road bullet
#           section removed entirely, and the raw R/B tail strings quoted
#           literally inline so low-level symbol detail still differs
#           concretely between any two inputs even within the same
#           archetype.
# ---------------------------------------------------------------------------

ROAD_NAME = {
    "bigEye": "Big Eye Boy",
    "small": "Small Road",
    "cockroach": "Cockroach Pig",
}
COLOR_WORD = {"R": "Red", "B": "Blue"}

ROAD_KEYS = ("bigEye", "small", "cockroach")


def _validate_tail(tail: DerivedTailSymbols) -> None:
    for field_name, value in (
        ("bigEye", tail.bigEye),
        ("small", tail.small),
        ("cockroach", tail.cockroach),
    ):
        bad = [c for c in value if c not in ("R", "B")]
        if bad:
            raise InvalidRoadsError(f"invalid symbols in {field_name}: {bad}")


def _trailing_streak(symbols: str) -> tuple[str | None, int]:
    if not symbols:
        return None, 0
    last = symbols[-1]
    n = 1
    for c in reversed(symbols[:-1]):
        if c == last:
            n += 1
        else:
            break
    return last, n


def _detect_chop(symbols: str, min_len: int = 4) -> bool:
    if len(symbols) < min_len:
        return False
    tail = symbols[-min_len:]
    return all(tail[i] != tail[i - 1] for i in range(1, len(tail)))


def _latest_colors(tail: DerivedTailSymbols) -> dict[str, str | None]:
    return {
        "bigEye": tail.bigEye[-1] if tail.bigEye else None,
        "small": tail.small[-1] if tail.small else None,
        "cockroach": tail.cockroach[-1] if tail.cockroach else None,
    }


def _longest_streak_for_color(tail: DerivedTailSymbols, color: str) -> tuple[str | None, int]:
    """Return (road_key, length) of the longest trailing streak of the
    given color across all three roads (None, 0 if no road ends in that
    color)."""
    best_key: str | None = None
    best_len = 0
    for key in ROAD_KEYS:
        last_color, length = _trailing_streak(getattr(tail, key))
        if last_color == color and length > best_len:
            best_key, best_len = key, length
    return best_key, best_len


def _raw_dump(tail: DerivedTailSymbols) -> str:
    return (
        f"Raw symbols — Big Eye Boy: {tail.bigEye or '(none)'}, "
        f"Small Road: {tail.small or '(none)'}, "
        f"Cockroach Pig: {tail.cockroach or '(none)'}."
    )


def describe_derived_in_nl(tail: DerivedTailSymbols) -> str:
    """Translate the three derived roads' tail symbols into a fixed-format
    English description used as the embedding input for both derived
    pattern seeding and runtime matching.

    Classifies the state into exactly one of five archetypes (mirroring
    the 5 "問路" categories this feature is built around) and writes a
    short narrative with an archetype-specific opening clause — each
    archetype uses deliberately different vocabulary from the very first
    word so there is no shared boilerplate prefix dragging unrelated
    archetypes together in embedding space (see version history above).
    The raw R/B strings are always quoted literally at the end so distinct
    inputs within the same archetype still produce distinguishable text.
    """
    _validate_tail(tail)

    latest = _latest_colors(tail)
    values = [v for v in latest.values() if v is not None]

    # 1. Three-way alignment (齊色 / 三元及第)
    if len(values) == 3 and all(v == values[0] for v in values):
        color_word = COLOR_WORD[values[0]]
        body = (
            f"Full house: Big Eye Boy, Small Road, and Cockroach Pig have all landed on "
            f"{color_word} at the exact same moment. This triple agreement across three "
            f"independent historical comparison spans is the rarest and most trusted "
            f"baccarat road omen — 三元及第."
        )
        return f"{body}\n\n{_raw_dump(tail)}"

    # 2. Extended blue streak -> rebound watch (反彈 / 逢藍知返), checked
    #    before the red dragon case since 3+ consecutive blue is itself a
    #    distinct, time-critical signal.
    road_key, blue_len = _longest_streak_for_color(tail, "B")
    if road_key is not None and blue_len >= 3:
        road_name = ROAD_NAME[road_key]
        body = (
            f"Overdue bounce: {road_name} has now gone Blue {blue_len} times in a row "
            f"without a break. A run this long rarely continues forever — the longer the "
            f"disorder drags on, the more probability leans toward a reversal snapping back "
            f"to Red — 逢藍知返."
        )
        return f"{body}\n\n{_raw_dump(tail)}"

    # 3. Sustained red dragon on a single road (連龍 / 下三路連龍)
    road_key, red_len = _longest_streak_for_color(tail, "R")
    if road_key is not None and red_len >= 4:
        road_name = ROAD_NAME[road_key]
        body = (
            f"Dragon alert: {road_name} alone is riding an unbroken run of {red_len} Red "
            f"results. Even when the Big Road itself looks tangled and irregular on its "
            f"face, a dragon this long on a single derived road proves the deeper rhythm at "
            f"that historical offset is rock solid — 下三路連龍."
        )
        return f"{body}\n\n{_raw_dump(tail)}"

    # 4. Alternating chop rhythm (單跳 / 下三路單跳)
    chop_roads = [ROAD_NAME[k] for k in ROAD_KEYS if _detect_chop(getattr(tail, k))]
    if chop_roads:
        body = (
            f"Metronome rhythm: {', '.join(chop_roads)} keeps flipping color on every "
            f"single step, swinging back and forth like clockwork between a regular state "
            f"and an irregular state — 下三路單跳."
        )
        return f"{body}\n\n{_raw_dump(tail)}"

    # 5. Majority two-one complement split (互補 / 三路互補)
    if len(values) == 3:
        red_count = values.count("R")
        blue_count = values.count("B")
        if red_count == 2 and blue_count == 1:
            odd_key = next(k for k in ROAD_KEYS if latest[k] == "B")
            body = (
                f"Split vote: two of the three derived roads currently agree on Red while "
                f"{ROAD_NAME[odd_key]} alone breaks rank with Blue. One dimension of "
                f"symmetry has cracked, but the remaining two still hold, so the broader "
                f"inertia likely keeps leaning Red — 三路互補."
            )
            return f"{body}\n\n{_raw_dump(tail)}"
        if blue_count == 2 and red_count == 1:
            odd_key = next(k for k in ROAD_KEYS if latest[k] == "R")
            body = (
                f"Split vote: two of the three derived roads currently agree on Blue while "
                f"{ROAD_NAME[odd_key]} alone breaks rank with Red. One dimension of "
                f"symmetry has cracked, but the remaining two still hold, so the broader "
                f"inertia likely keeps leaning Blue — 三路互補."
            )
            return f"{body}\n\n{_raw_dump(tail)}"

    # 6. Fallback: no dominant structure detected
    body = (
        "Flat read: the three derived roads show no full-house agreement, no sustained "
        "dragon run, no alternating chop, and no majority split right now — the underlying "
        "Big Road structure at this point is simply noisy."
    )
    return f"{body}\n\n{_raw_dump(tail)}"
