import json
import os

import pytest

from app.services.derived_roads import (
    DerivedTailSymbols,
    InvalidRoadsError,
    ask_next,
    compute_all_roads,
    compute_big_road,
    compute_derived_road,
    describe_derived_in_nl,
    extract_tail_symbols,
    tail_symbols,
)

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "road_cases.json")


def _cells_as_dicts(cells):
    return [vars(c) for c in cells]


@pytest.fixture(scope="module")
def fixture_cases():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_fixture_file_matches_live_computation(fixture_cases):
    """Regenerating the fixture from the current implementation must be a
    no-op — this guards against silently drifting the algorithm without
    regenerating road_cases.json (which the frontend also relies on for its
    own parity check)."""
    for case in fixture_cases:
        roads = compute_all_roads(list(case["input"]))
        assert _cells_as_dicts(roads.bigRoad) == case["bigRoad"], case["input"]
        assert _cells_as_dicts(roads.bigEye) == case["bigEye"], case["input"]
        assert _cells_as_dicts(roads.small) == case["small"], case["input"]
        assert _cells_as_dicts(roads.cockroach) == case["cockroach"], case["input"]


def test_simple_streak_no_tail():
    # BBBBB: 5 Bankers, column 0, rows 0-4, no tailing yet (ROWS=6)
    cells = compute_big_road(list("BBBBB"))
    assert [vars(c) for c in cells] == [
        {"col": 0, "row": 0, "symbol": "B", "tieCount": 0},
        {"col": 0, "row": 1, "symbol": "B", "tieCount": 0},
        {"col": 0, "row": 2, "symbol": "B", "tieCount": 0},
        {"col": 0, "row": 3, "symbol": "B", "tieCount": 0},
        {"col": 0, "row": 4, "symbol": "B", "tieCount": 0},
    ]


def test_streak_tails_right_at_row_5():
    # 8 Bankers: rows 0-5 fill column 0, then tail right for the 7th and 8th.
    cells = compute_big_road(list("BBBBBBBB"))
    cols = [c.col for c in cells]
    rows = [c.row for c in cells]
    assert cols == [0, 0, 0, 0, 0, 0, 1, 2]
    assert rows == [0, 1, 2, 3, 4, 5, 5, 5]


def test_break_after_tail_starts_next_column_after_tail():
    # 8 Bankers then a Player: the Player should open a new column right
    # after the last tail column (col=2), i.e. col=3, row=0.
    cells = compute_big_road(list("BBBBBBBBP"))
    last = cells[-1]
    assert last.col == 3
    assert last.row == 0
    assert last.symbol == "P"


def test_tie_does_not_open_column_and_overlays_tiecount():
    cells = compute_big_road(list("BBT TP".replace(" ", "")))
    # "BBTTP" -> B(0,0) B(0,1) tie x2 attach to last B cell, P opens col1 row0
    assert cells[0].col == 0 and cells[0].row == 0 and cells[0].tieCount == 0
    assert cells[1].col == 0 and cells[1].row == 1 and cells[1].tieCount == 2
    assert cells[2].col == 1 and cells[2].row == 0 and cells[2].symbol == "P"


def test_leading_ties_attach_to_first_resolved_outcome():
    cells = compute_big_road(list("TTB"))
    assert _cells_as_dicts(cells) == [
        {"col": 0, "row": 0, "symbol": "B", "tieCount": 2}
    ]


def test_ties_only_shoe_keeps_visible_placeholder():
    cells = compute_big_road(list("TT"))
    assert _cells_as_dicts(cells) == [
        {"col": 0, "row": 0, "symbol": "T", "tieCount": 2}
    ]


@pytest.mark.parametrize(
    "results,offset",
    [
        ("BBBBBBB" + "P" * 6, 1),
        ("BBBBBBB" + "P" + "B" * 6, 2),
        ("BBBBBBB" + "P" + "B" + "P" * 6, 3),
    ],
)
def test_derived_road_compares_occupied_tail_row(results, offset):
    big_road = compute_big_road(list(results))
    derived = compute_derived_road(big_road, offset)

    # In each sequence the final Big Road cell is at row 5, and the compared
    # column contains a single tail bead at row 5. Its column height is one,
    # but the matching row is occupied, so the derived symbol must be red.
    assert big_road[-1].row == 5
    assert derived[-1].color == "R"


def test_derived_road_requires_minimum_columns():
    # Big Eye Boy (offset=1) needs at least column index 1 to produce any
    # symbol; Small Road (offset=2) needs column index 2; Cockroach (offset=3)
    # needs column index 3.
    big_road = compute_big_road(list("BP"))  # only 2 columns (col 0, col 1)
    big_eye = compute_derived_road(big_road, 1)
    small = compute_derived_road(big_road, 2)
    cockroach = compute_derived_road(big_road, 3)
    assert len(big_eye) >= 0  # col=1,row=0 needs left2=col-2=-1 -> no symbol yet
    assert small == []
    assert cockroach == []


def test_tail_symbols_extraction():
    big_road = compute_big_road(list("BPBPBPBPBPBPBPBP"))
    road = compute_derived_road(big_road, 1)
    tail = tail_symbols(road, k=4)
    assert len(tail) <= 4
    assert all(c in ("R", "B") for c in tail)


def test_extract_tail_symbols_and_describe_roundtrip():
    results = list("BBBBBBPPPPPPBBBBBBPPPPPP")
    roads = compute_all_roads(results)
    tail = extract_tail_symbols(roads, k=12)
    assert isinstance(tail, DerivedTailSymbols)
    text = describe_derived_in_nl(tail)
    assert "Raw symbols" in text
    assert "Big Eye Boy" in text
    assert "Small Road" in text
    assert "Cockroach Pig" in text


def test_describe_derived_invalid_symbols_raises():
    with pytest.raises(InvalidRoadsError):
        describe_derived_in_nl(DerivedTailSymbols(bigEye="RRX", small="RR", cockroach="R"))


def test_describe_derived_all_red_alignment():
    tail = DerivedTailSymbols(bigEye="RRR", small="RR", cockroach="R")
    text = describe_derived_in_nl(tail)
    assert "Full house" in text
    assert "三元及第" in text


def test_describe_derived_chop_signal():
    # bigEye alone alternates on its last 4 symbols; small/cockroach too
    # short to register their own chop, so this should classify as chop.
    tail = DerivedTailSymbols(bigEye="RBRB", small="RB", cockroach="R")
    text = describe_derived_in_nl(tail)
    assert "Metronome rhythm" in text
    assert "Big Eye Boy" in text
    assert "下三路單跳" in text


def test_describe_derived_rebound_signal():
    tail = DerivedTailSymbols(bigEye="BBB", small="R", cockroach="R")
    text = describe_derived_in_nl(tail)
    assert "Overdue bounce" in text
    assert "逢藍知返" in text


def test_describe_derived_dragon_signal():
    tail = DerivedTailSymbols(bigEye="RRRR", small="RB", cockroach="BR")
    text = describe_derived_in_nl(tail)
    assert "Dragon alert" in text
    assert "下三路連龍" in text


def test_describe_derived_complement_signal():
    tail = DerivedTailSymbols(bigEye="R", small="R", cockroach="B")
    text = describe_derived_in_nl(tail)
    assert "Split vote" in text
    assert "三路互補" in text


def test_ask_next_returns_both_hypotheticals():
    results = list("BBBBBBPPPPPPBBBBBB")
    out = ask_next(results)
    assert "ifBanker" in out and "ifPlayer" in out
    assert isinstance(out["ifBanker"], DerivedTailSymbols)
    assert isinstance(out["ifPlayer"], DerivedTailSymbols)
