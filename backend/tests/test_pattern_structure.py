"""Tests for pattern_structure.py: the structural-category classifier that
replaced the earlier `minWindowLen` raw-length guard in match_engine.py."""

from __future__ import annotations

from app.services.pattern_structure import (
    BREAK_END,
    BREAK_RESUME,
    CHOP,
    COMPLEX,
    CONTINUOUS_RUN,
    classify_structure,
    compatible_categories,
)

# --------------------------------------------------------------------------
# classify_structure: the 10 default patterns + custom examples
# --------------------------------------------------------------------------


def test_classify_continuous_run_patterns():
    assert classify_structure(list("BBBBBB")) == CONTINUOUS_RUN  # 長莊連龍
    assert classify_structure(list("PPPPPP")) == CONTINUOUS_RUN  # 長閒連龍


def test_classify_break_end_patterns():
    assert classify_structure(list("BBBBBBP")) == BREAK_END  # 長莊斷龍
    assert classify_structure(list("PPPPPPB")) == BREAK_END  # 長閒斷龍


def test_classify_break_resume_pattern():
    assert classify_structure(list("BBBBPBBBB")) == BREAK_RESUME  # 莊龍回頭


def test_classify_chop_patterns():
    assert classify_structure(list("BPBPBPBP")) == CHOP  # 單跳
    assert classify_structure(list("BBPPBBPP")) == CHOP  # 雙雙跳
    assert classify_structure(list("BBPPBB")) == CHOP  # 拍拍黐
    assert classify_structure(list("BPPBPPBPP")) == CHOP  # 一房兩廳


def test_classify_tie_involved_pattern_falls_back_to_chop_or_complex():
    # "和局夾擊" (BPTBPTB) - Ties are dropped for structural classification,
    # leaving B/P runs of length 1 each, which satisfies the CHOP shape.
    assert classify_structure(list("BPTBPTB")) == CHOP


def test_classify_business_user_example_with_different_exact_lengths():
    """A business user defining a custom pattern with [(B,3),(P,2),(B,2)]
    instead of the exact [(B,4),(P,1),(B,4)] used by "莊龍回頭" should still
    land in the same break_resume category - the classifier works on
    relative long/short thresholds, not exact numbers from one pattern."""
    assert classify_structure(list("BBBPPBB")) == BREAK_RESUME


# --------------------------------------------------------------------------
# compatible_categories: live, still-unfolding windows
# --------------------------------------------------------------------------


def test_short_uninterrupted_window_is_ambiguous_between_continuous_and_break_resume():
    """A plain "BBBB" window (no interruption has happened yet) is a live,
    not-yet-falsified candidate for BOTH continuous_run and break_resume -
    genuine ambiguity, not a bug (see match_engine's alsoConsistentWith)."""
    cats = compatible_categories(list("BBBB"))
    assert CONTINUOUS_RUN in cats
    assert BREAK_RESUME in cats
    assert BREAK_END in cats
    assert COMPLEX in cats


def test_window_with_interruption_excludes_continuous_run():
    """Once a window shows any side-switch, continuous_run is permanently
    falsified - this is a real logical fact, not an approximation."""
    cats = compatible_categories(list("BBBBP"))
    assert CONTINUOUS_RUN not in cats


def test_window_mid_resumption_only_compatible_with_break_resume():
    """The real production regression case: a 7-round window "BBBBPBB"
    (莊×4, 閒×1, 莊×2-in-progress) must remain eligible for break_resume
    (莊龍回頭) and must exclude chop (拍拍黐 - whose first run target of 2
    has already been exceeded by the window's actual first run of 4) and
    break_end (長莊斷龍 - which only ever has exactly 2 runs, but the window
    already has 3)."""
    cats = compatible_categories(list("BBBBPBB"))
    assert BREAK_RESUME in cats
    assert CHOP not in cats
    assert BREAK_END not in cats
    assert CONTINUOUS_RUN not in cats


def test_window_resumed_run_long_enough_readmits_continuous_run():
    """Regression test: once the *current* (post-interruption) run itself
    grows long enough (>= MAIN_RUN_MIN), continuous_run should become a live
    candidate again alongside break_resume - letting vector-search score
    and alsoConsistentWith decide between "it recovered from a break" vs
    "a fresh long dragon is happening right now", instead of continuous_run
    being permanently vetoed by one earlier interruption no matter how long
    the resumed streak later becomes."""
    cats = compatible_categories(list("BBBBPBBB"))  # resumed run = 3
    assert BREAK_RESUME in cats
    assert CONTINUOUS_RUN in cats


def test_window_resumed_run_still_short_does_not_readmit_continuous_run():
    """The boundary case right below the threshold: resumed run of only 2
    should NOT yet readmit continuous_run (matches the existing
    test_window_mid_resumption_only_compatible_with_break_resume case)."""
    cats = compatible_categories(list("BBBBPBB"))  # resumed run = 2
    assert CONTINUOUS_RUN not in cats


def test_chop_window_tail_short_does_not_readmit_continuous_run():
    """A genuine chop window (all short runs) should not spuriously gain
    continuous_run just because its last run happens to be non-empty - the
    tail run must actually reach MAIN_RUN_MIN to qualify."""
    cats = compatible_categories(list("BBPPBB"))  # tail run = 2, still short
    assert CONTINUOUS_RUN not in cats


def test_window_with_extra_run_after_resume_excludes_break_end():
    """Once a window has 3 runs, break_end (which requires exactly 2) is
    permanently excluded, regardless of the individual run lengths."""
    cats = compatible_categories(list("BBBBBBP"))  # 2 runs so far: still live
    assert BREAK_END in cats
    cats_after_third_run = compatible_categories(list("BBBBBBPB"))  # now 3 runs
    assert BREAK_END not in cats_after_third_run


def test_chop_excluded_once_a_run_exceeds_the_short_threshold():
    """A window whose first run already exceeds the chop-category's "short"
    cap (<=2) can never become a chop pattern, even if it later alternates
    rapidly."""
    cats = compatible_categories(list("BBB"))  # single run of 3, already > 2
    assert CHOP not in cats


def test_empty_bp_window_all_ties_rules_nothing_out():
    cats = compatible_categories(list("TTT"))
    assert cats == {CONTINUOUS_RUN, BREAK_RESUME, BREAK_END, CHOP, COMPLEX}


def test_complex_always_included_as_safe_fallback():
    for window in ("BBBB", "BBBBP", "BBBBPBB", "BPBPBP", "TTT"):
        assert COMPLEX in compatible_categories(list(window))
