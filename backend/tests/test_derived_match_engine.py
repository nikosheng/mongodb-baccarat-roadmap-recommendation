"""Unit tests for derived_match_engine.match_derived, using mocked Mongo +
embedder so no real Atlas/Voyage connection is needed. (The project has no
mongomock/test-DB fixture infrastructure — existing tests are all pure
unit tests; this follows the same pattern via unittest.mock.)

For a true end-to-end check against real Atlas + Voyage, see the manual
verification steps in the PR description / README; this suite only
verifies match_derived's control flow (threshold flagging, no-data
short-circuit, persistence call) in isolation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import derived_match_engine


@pytest.mark.asyncio
async def test_match_derived_returns_none_with_no_rounds():
    with patch.object(derived_match_engine, "get_rounds_sequence", AsyncMock(return_value=[])):
        result = await derived_match_engine.match_derived("shoe1", 1)
    assert result is None


@pytest.mark.asyncio
async def test_match_derived_returns_none_with_insufficient_columns():
    # Only 2 Big Road columns -> no derived road has produced a symbol yet.
    with patch.object(derived_match_engine, "get_rounds_sequence", AsyncMock(return_value=list("BP"))):
        result = await derived_match_engine.match_derived("shoe1", 2)
    assert result is None


@pytest.mark.asyncio
async def test_match_derived_flags_low_confidence_below_threshold():
    fake_db = MagicMock()
    fake_db.derived_patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "abc123",
                "name": "三元及第",
                "predictedNext": "B",
                "baseConfidence": 0.6,
                "score": 0.5,  # below threshold
            }
        ]
    )
    fake_db.derived_matches.insert_one = AsyncMock()

    results = list("BBBBBBPPPPPPBBBBBBPPPPPP")  # enough columns for all 3 derived roads

    with (
        patch.object(derived_match_engine, "get_rounds_sequence", AsyncMock(return_value=results)),
        patch.object(derived_match_engine, "get_db", return_value=fake_db),
        patch("app.services.derived_match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await derived_match_engine.match_derived("shoe1", len(results))

    assert result is not None
    assert len(result.topMatches) == 1
    assert result.topMatches[0].lowConfidence is True
    assert result.noMatch is False
    fake_db.derived_matches.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_derived_high_confidence_above_threshold():
    fake_db = MagicMock()
    fake_db.derived_patterns.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {
                "_id": "abc123",
                "name": "三元及第",
                "predictedNext": "B",
                "baseConfidence": 0.6,
                "score": 0.95,  # above threshold (0.82)
            },
            {
                "_id": "def456",
                "name": "下三路連龍",
                "predictedNext": "B",
                "baseConfidence": 0.58,
                "score": 0.70,
            },
        ]
    )
    fake_db.derived_matches.insert_one = AsyncMock()

    results = list("BBBBBBPPPPPPBBBBBBPPPPPP")

    with (
        patch.object(derived_match_engine, "get_rounds_sequence", AsyncMock(return_value=results)),
        patch.object(derived_match_engine, "get_db", return_value=fake_db),
        patch("app.services.derived_match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await derived_match_engine.match_derived("shoe1", len(results))

    assert result is not None
    assert result.topMatches[0].lowConfidence is False
    assert result.topMatches[1].lowConfidence is True
    assert result.noMatch is False


@pytest.mark.asyncio
async def test_match_derived_no_hits_returns_no_match_true():
    fake_db = MagicMock()
    fake_db.derived_patterns.aggregate.return_value.to_list = AsyncMock(return_value=[])
    fake_db.derived_matches.insert_one = AsyncMock()

    results = list("BBBBBBPPPPPPBBBBBBPPPPPP")

    with (
        patch.object(derived_match_engine, "get_rounds_sequence", AsyncMock(return_value=results)),
        patch.object(derived_match_engine, "get_db", return_value=fake_db),
        patch("app.services.derived_match_engine.embed_text", AsyncMock(return_value=[0.1] * 1024)),
    ):
        result = await derived_match_engine.match_derived("shoe1", len(results))

    assert result is not None
    assert result.noMatch is True
    assert result.topMatches == []
