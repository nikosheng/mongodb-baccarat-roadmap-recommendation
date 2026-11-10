"""Unit tests for match_engine, using mocked Mongo + embedder so no real
Atlas/Voyage connection is needed (same approach as test_derived_match_engine.py).

Focus: the deterministic `structuralCategory` guard in
vector_search_patterns/match_window — a pattern is only eligible if its
coarse narrative shape (continuous run / break-then-resume / break-end /
chop, see pattern_structure.py) hasn't been ruled out by what has actually
happened in the live window so far. This supersedes an earlier, cruder
`minWindowLen` raw-length cutoff: that caught the worst false positives
(e.g. a plain 4-round "BBBB" window being misclassified as a 9-round
"long streak interrupted then resumed" custom pattern purely from embedding
coincidence) but also wrongly excluded genuinely in-progress multi-phase
narratives (e.g. a 7-round window mid-way through re-enacting that same
9-round pattern).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import match_engine


@pytest.mark.asyncio
async def test_match_window_returns_none_with_insufficient_rounds():
    with patch.object(match_engine, "get_recent_window", AsyncMock(return_value=["B", "B"])):
        result = await match_engine.match_window("shoe1", 2)
    assert result is None


@pytest.mark.asyncio
async def test_match_window_excludes_structurally_incompatible_patterns():
    """Regression test: a 4-round window ("BBBB") must not be matched
    against a "break_resume"-category custom pattern whose raw vector-search
    score happens to be higher, when a genuinely-eligible "continuous_run"
    pattern is also a candidate... except BBBB with no interruption at all
    is actually still a *live* candidate for break_resume too (nothing has
    ruled it out yet - see pattern_structure.compatible_categories). What
    IS structurally impossible for a plain "BBBB" window is a "chop"
    category pattern (which requires every run to already be short, and
    "BBBB" already has a run of 4) - this test exercises that exclusion."""
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "chop-pattern-id",
                "name": "拍拍黐",
                "predictedNext": "P",
                "baseConfidence": 0.53,
                "structuralCategory": "chop",
                "score": 0.90,  # highest raw score, but structurally impossible
            },
            {
                "_id": "eligible-pattern-id",
                "name": "長莊連龍",
                "predictedNext": "B",
                "baseConfidence": 0.6,
                "structuralCategory": "continuous_run",
                "score": 0.83,  # lower raw score, but the only genuinely eligible one
            },
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=["B", "B", "B", "B"])),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 4)

    assert result is not None
    assert result.noMatch is False
    names = [m.name for m in result.topMatches]
    assert "拍拍黐" not in names
    assert names == ["長莊連龍"]


@pytest.mark.asyncio
async def test_match_window_allows_in_progress_multiphase_pattern():
    """Regression test for the real production bug this structural filter
    was designed to fix without over-correcting: a 7-round window
    "BBBBPBB" (long Banker run, brief Player interruption, Banker resuming)
    is genuinely mid-way through a "break_resume" narrative and MUST remain
    eligible for a break_resume-category pattern, even though it hasn't
    finished (an earlier length-based `minWindowLen` cutoff wrongly
    excluded this case)."""
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "break-resume-id",
                "name": "莊龍回頭",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "break_resume",
                "score": 0.9333,
            },
            {
                "_id": "break-end-id",
                "name": "長莊斷龍",
                "predictedNext": "P",
                "baseConfidence": 0.6,
                "structuralCategory": "break_end",
                "score": 0.9304,  # structurally excluded: window already has 3 runs
            },
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=list("BBBBPBB"))),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 7)

    assert result is not None
    assert result.noMatch is False
    names = [m.name for m in result.topMatches]
    assert names == ["莊龍回頭"]


@pytest.mark.asyncio
async def test_match_window_resumed_run_readmits_continuous_run_as_also_consistent():
    """Regression test for the "theoretically this should also match 長莊連龍"
    report: once the post-interruption run itself grows long enough
    (window "BBBBPBBB", resumed run = 3), a continuous_run-category pattern
    becomes structurally eligible again alongside break_resume - it should
    no longer be permanently vetoed just because an interruption happened
    earlier in the window. When their scores are close, the formal
    recommendation still only surfaces the single top pick, but the near-tie
    is honestly reported via alsoConsistentWith rather than silently hidden."""
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "break-resume-id",
                "name": "莊龍回頭",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "break_resume",
                "score": 0.9344,
            },
            {
                "_id": "continuous-run-id",
                "name": "長莊連龍",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "continuous_run",
                "score": 0.9338,  # gap 0.0006 <= epsilon (0.01) -> genuine tie
            },
            {
                "_id": "break-end-id",
                "name": "長莊斷龍",
                "predictedNext": "P",
                "baseConfidence": 0.6,
                "structuralCategory": "break_end",
                "score": 0.93,  # structurally excluded: window already has 3 runs
            },
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=list("BBBBPBBB"))),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 8)

    assert result is not None
    # The formal recommendation only ever surfaces a single pick...
    names = [m.name for m in result.topMatches]
    assert names == ["莊龍回頭"]
    # ...but the near-tied continuous_run candidate (now structurally
    # eligible thanks to the long-enough resumed run) is still honestly
    # reported via alsoConsistentWith, and the still-ineligible break_end
    # candidate never appears anywhere.
    assert result.topMatches[0].alsoConsistentWith == ["長莊連龍"]


@pytest.mark.asyncio
async def test_match_window_no_eligible_candidates_returns_no_match():
    """If every raw hit's structural category has been ruled out by the
    window's own run history, the result must be a clean no-match rather
    than surfacing an ineligible pattern."""
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "chop-pattern-id",
                "name": "拍拍黐",
                "predictedNext": "P",
                "baseConfidence": 0.53,
                "structuralCategory": "chop",
                "score": 0.90,
            },
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=["B", "B", "B", "B"])),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 4)

    assert result is not None
    assert result.noMatch is True
    assert result.topMatches == []


@pytest.mark.asyncio
async def test_match_window_flags_low_confidence_below_threshold():
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "abc123",
                "name": "長莊連龍",
                "predictedNext": "B",
                "baseConfidence": 0.6,
                "structuralCategory": "continuous_run",
                "score": 0.70,  # below PATTERN_MIN_SCORE=0.82
            }
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=["B", "B", "B", "B"])),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 4)

    assert result is not None
    assert result.noMatch is False
    assert len(result.topMatches) == 1
    assert result.topMatches[0].lowConfidence is True


@pytest.mark.asyncio
async def test_match_window_flags_tied_candidates_as_also_consistent():
    """When two structurally-eligible candidates score within
    pattern_tie_epsilon of each other, the top pick should honestly surface
    the other as `alsoConsistentWith` instead of silently picking one -
    this is the genuine, acceptable ambiguity of an early/short window
    (e.g. a plain "BBBB" window is a live candidate for both a continuous
    run and the early stage of a break-then-resume narrative)."""
    fake_db = MagicMock()
    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "break-resume-id",
                "name": "莊龍回頭",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "break_resume",
                "score": 0.8281,
            },
            {
                "_id": "continuous-run-id",
                "name": "長莊連龍",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "continuous_run",
                "score": 0.8037,  # gap 0.0244 > epsilon (0.01) -> NOT a tie
            },
        ]
    )
    fake_db.matches.insert_one = AsyncMock()

    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=["B", "B", "B", "B"])),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 4)

    assert result is not None
    # Gap is larger than the configured tie epsilon, so this should NOT be
    # flagged as a tie.
    assert result.topMatches[0].alsoConsistentWith == []

    fake_db.patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "break-resume-id",
                "name": "莊龍回頭",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "break_resume",
                "score": 0.9333,
            },
            {
                "_id": "close-id",
                "name": "假設的近似候選",
                "predictedNext": "B",
                "baseConfidence": 0.55,
                "structuralCategory": "break_resume",
                "score": 0.9324,  # gap 0.0009 <= epsilon (0.01) -> genuine tie
            },
        ]
    )
    with (
        patch.object(match_engine, "get_recent_window", AsyncMock(return_value=list("BBBBPBB"))),
        patch.object(match_engine, "get_db", return_value=fake_db),
        patch("app.services.match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await match_engine.match_window("shoe1", 7)

    assert result is not None
    assert result.topMatches[0].name == "莊龍回頭"
    assert result.topMatches[0].alsoConsistentWith == ["假設的近似候選"]
