"""Voyage AI embedding client wrapper.

Exposes a single `embed_text(text, mode)` async function used by both
pattern seeding ("document" mode) and runtime window matching
("query" mode) — Voyage optimizes asymmetric retrieval differently for
each input_type.

A deterministic mock embedder is available via USE_MOCK_EMBEDDER=true
for offline development without a Voyage API key: it hashes the text
into a reproducible unit vector so the full pipeline (including
vector search) can be exercised end-to-end, though match quality will
not reflect real semantic similarity.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from functools import lru_cache
from typing import Literal

import numpy as np
import voyageai

from app.config import get_settings

logger = logging.getLogger(__name__)

EmbedMode = Literal["document", "query"]


class EmbedderError(RuntimeError):
    pass


def _mock_embed(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding derived from a text hash. Only for
    local development/testing without API keys — NOT semantically meaningful."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


@lru_cache
def _get_voyage_client() -> voyageai.Client:
    settings = get_settings()
    if not settings.voyage_api_key:
        raise EmbedderError(
            "VOYAGE_API_KEY is not set. Set it in .env or enable USE_MOCK_EMBEDDER=true."
        )
    return voyageai.Client(
        api_key=settings.voyage_api_key,
        base_url=settings.voyage_base_url,
    )


async def embed_text(text: str, mode: EmbedMode = "query") -> list[float]:
    """Embed a single text string. Returns a list[float] of length voyage_dim."""
    vectors = await embed_texts([text], mode=mode)
    return vectors[0]


async def embed_texts(texts: list[str], mode: EmbedMode = "document") -> list[list[float]]:
    """Batch-embed multiple texts in one API call (Voyage supports batching
    natively, which is far cheaper/faster than one-by-one calls)."""
    settings = get_settings()

    if settings.use_mock_embedder:
        return [_mock_embed(t, settings.voyage_dim) for t in texts]

    client = _get_voyage_client()

    def _call():
        return client.embed(
            texts,
            model=settings.voyage_model,
            input_type=mode,
        )

    try:
        result = await asyncio.to_thread(_call)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Voyage embedding call failed")
        raise EmbedderError(f"Voyage embedding failed: {exc}") from exc

    return result.embeddings
