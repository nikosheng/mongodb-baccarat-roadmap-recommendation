"""Natural-language pattern definition parser using Azure OpenAI.

Converts a free-form description like "連三莊之後連三閒,下盤多半出莊"
into a structured NLParseResult (name, category, canonicalSequence,
predictedNext, baseConfidence). This DSL step is only used to bootstrap
the pattern's canonicalSequence and metadata — the actual matching at
runtime is pure vector search against the embedded nlDescription/
canonicalSequence text, not this DSL.
"""

from __future__ import annotations

import json
import logging
import random

from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.models.schemas import NLParseResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a baccarat (百家樂) road-pattern (路數) analysis expert.
The user will describe a betting-road pattern in Chinese or English. Parse it into JSON.

Baccarat outcomes are encoded as single letters: B = Banker (莊), P = Player (閒), T = Tie (和).

Output STRICT JSON with exactly these fields:
{
  "name": "short Chinese name for this pattern, 2-6 characters",
  "category": "one of: streak | chop | mixed | tie | ratio | custom",
  "canonicalSequence": "a representative example sequence using only letters B/P/T, length 3-15",
  "predictedNext": "B | P | T  (the outcome this pattern predicts for the NEXT round)",
  "baseConfidence": a float between 0.45 and 0.75 representing how strongly this pattern predicts the next outcome,
  "rationale": "one sentence in Chinese explaining the reasoning"
}

Only output the JSON object, no markdown fences, no extra text.

Example input: 連三莊之後連三閒,下盤多半出莊
Example output:
{"name": "三莊三閒切換", "category": "mixed", "canonicalSequence": "BBBPPP", "predictedNext": "B", "baseConfidence": 0.55, "rationale": "三莊三閒的切換結構暗示下一輪會轉回莊"}
"""


class NLParseError(RuntimeError):
    pass


def _mock_parse(text: str) -> NLParseResult:
    """Deterministic fallback parser for offline dev without Azure OpenAI
    credentials. Very naive heuristic, only for exercising the pipeline."""
    seq_options = ["BBBPPP", "BPBPBP", "BBPPBB", "PPPBBB", "BBBBBP"]
    seq = random.choice(seq_options)
    next_outcome = random.choice(["B", "P", "T"])
    return NLParseResult(
        name="自訂路數",
        category="custom",
        canonicalSequence=seq,
        predictedNext=next_outcome,
        baseConfidence=0.55,
        rationale=f"(mock parser) 基於輸入文字 '{text[:20]}...' 產生的示意結果",
    )


async def parse_nl_pattern(text: str) -> NLParseResult:
    settings = get_settings()

    if settings.use_mock_llm:
        return _mock_parse(text)

    if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
        raise NLParseError(
            "Azure OpenAI is not configured. Set AZURE_OPENAI_* in .env or enable USE_MOCK_LLM=true."
        )

    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return NLParseResult(**data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Azure OpenAI NL parse failed")
        raise NLParseError(f"Failed to parse pattern: {exc}") from exc
