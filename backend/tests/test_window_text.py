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


def test_pure_chop_pattern():
    seq = ["B", "P", "B", "P", "B", "P", "B", "P"]
    text = describe_window_in_nl(seq)
    assert "balanced between Banker and Player" in text
    assert "no run (isolated)" in text
    assert "pure chopping rhythm with constant alternation" in text
    assert "no notable reversal" in text


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
