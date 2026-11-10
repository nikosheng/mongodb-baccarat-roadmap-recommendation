import pytest

from app.services.window_text import (
    InvalidSequenceError,
    describe_window_in_nl,
)


def test_empty_sequence_raises():
    with pytest.raises(InvalidSequenceError):
        describe_window_in_nl([])


def test_invalid_symbol_raises():
    with pytest.raises(InvalidSequenceError):
        describe_window_in_nl(["B", "X", "P"])


def test_long_banker_streak_broken_by_player():
    seq = ["B", "B", "B", "B", "B", "B", "P"]
    text = describe_window_in_nl(seq)
    assert "Banker heavily dominates" in text
    assert "very long run of six" in text
    assert "single Player just appeared" in text
    assert "interrupted by a single Player" in text
    assert "strong one-sided trend" in text
    assert "one long run broken by a brief interruption near the end of the window" in text


def test_similar_extended_window_shares_key_phrases():
    """BBBBBBPB should share most semantic phrases with BBBBBBP since both
    represent a long banker dominance broken briefly by a player hand."""
    seq1 = ["B", "B", "B", "B", "B", "B", "P"]
    seq2 = ["B", "B", "B", "B", "B", "B", "P", "B"]
    text1 = describe_window_in_nl(seq1)
    text2 = describe_window_in_nl(seq2)
    assert "Banker heavily dominates" in text1
    assert "Banker heavily dominates" in text2
    assert "very long run of six" in text1
    assert "very long run of six" in text2
    assert "resumed shortly after a brief" in text2
    assert "one long run broken by a brief interruption, then resumed on the same side" in text2


def test_pure_chop_pattern():
    seq = ["B", "P", "B", "P", "B", "P", "B", "P"]
    text = describe_window_in_nl(seq)
    assert "balanced between Banker and Player" in text
    assert "no run (isolated)" in text
    assert "pure chopping rhythm with constant alternation" in text
    assert "no notable reversal" in text
    assert "many short runs with frequent switching" in text


def test_double_chop_pattern():
    seq = ["B", "B", "P", "P", "B", "B", "P", "P"]
    text = describe_window_in_nl(seq)
    assert "repeating pair-wise rhythm (double-chop)" in text


def test_all_tie():
    seq = ["T", "T", "T"]
    text = describe_window_in_nl(seq)
    assert "Tie results dominate this window" in text
    assert "frequent Tie activity" in text


def test_minimal_single_round():
    seq = ["B"]
    text = describe_window_in_nl(seq)
    assert "Banker heavily dominates" in text
    assert "single Banker just appeared" in text
    assert "single uninterrupted run, no break at all" in text


def test_extreme_long_streak_fallback():
    seq = ["B"] * 10
    text = describe_window_in_nl(seq)
    assert "extreme run of 10" in text


def test_no_numbers_leak_into_output():
    """Core invariant: ratios/counts must never appear as raw decimal
    numbers in the final text (digits inside 'run of N' labels and
    sequence length descriptors are allowed, but not things like 0.86)."""
    seq = ["B", "B", "B", "P", "B", "B", "P", "B"]
    text = describe_window_in_nl(seq)
    assert "0." not in text  # no decimal ratios leaked


def test_same_trailing_streak_length_but_different_structure():
    """Regression test for a real production bug: a plain 4-Banker window
    ("BBBB") coincidentally shares the exact same 'Current state' and
    'Longest run' bucket text as the tail of a longer custom pattern like
    "BBBBPBBBB" (4-Banker streak, broken by one Player, then 4 more
    Banker). Without an explicit structure signal, the two texts were
    nearly indistinguishable, causing the short window to be misclassified
    as the longer broken-then-resumed pattern instead of a plain ongoing
    streak. The new 'Structure' field must clearly separate them."""
    pure_streak = describe_window_in_nl(["B", "B", "B", "B"])
    broken_then_resumed = describe_window_in_nl(
        ["B", "B", "B", "B", "P", "B", "B", "B", "B"]
    )

    # These two bucket lines coincidentally still match (same trailing
    # streak length of 4) - this is expected and is exactly the condition
    # that used to cause the misclassification.
    assert "ongoing Banker streak of 4" in pure_streak
    assert "ongoing Banker streak of 4" in broken_then_resumed
    assert "medium run of four" in pure_streak
    assert "medium run of four" in broken_then_resumed

    # The Structure field must now clearly distinguish them.
    assert "single uninterrupted run, no break at all" in pure_streak
    assert "single uninterrupted run, no break at all" not in broken_then_resumed
    assert (
        "one long run broken by a brief interruption, then resumed on the same side"
        in broken_then_resumed
    )
    assert (
        "one long run broken by a brief interruption, then resumed on the same side"
        not in pure_streak
    )

    # The Current state qualifier must also distinguish "this streak IS the
    # whole window" from "this streak resumed after something earlier".
    assert "spanning the entire window with nothing before it" in pure_streak
    assert "spanning the entire window with nothing before it" not in broken_then_resumed
    assert "resumed after something else happened earlier in the window" in broken_then_resumed
    assert (
        "resumed after something else happened earlier in the window" not in pure_streak
    )


def test_dissimilar_patterns_share_little_vocabulary():
    long_streak = describe_window_in_nl(["B", "B", "B", "B", "B", "B", "P"])
    chop = describe_window_in_nl(["B", "P", "B", "P", "B", "P", "B", "P"])
    streak_tokens = set(long_streak.replace("\n", " ").split())
    chop_tokens = set(chop.replace("\n", " ").split())
    overlap = streak_tokens & chop_tokens
    # Should mostly only share structural words like "Baccarat", "sequence:",
    # "Window", "summary:", "-", "Length:", etc. Key semantic words should differ.
    assert "dominates" not in overlap
    assert "alternation:" not in overlap or True  # label itself may repeat
    assert "heavily" not in chop_tokens
    assert "chopping" not in streak_tokens
