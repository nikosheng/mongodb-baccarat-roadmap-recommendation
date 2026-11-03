"""Natural-language derived-road (下三路) pattern parser using Azure OpenAI.

Converts a free-form description like "大眼仔小路蟑螂路同時開紅,下盤續莊" into
a structured DerivedNLParseResult (name, category, canonicalRoads,
predictedNext, baseConfidence). Mirrors nl_pattern.py but the DSL targets
R/B tail-symbol strings for the three derived roads instead of a B/P/T
canonicalSequence.
"""

from __future__ import annotations

import json
import logging
import random

from openai import AsyncAzureOpenAI

from app.config import get_settings
from app.models.schemas import DerivedNLParseResult, DerivedTailSymbolsSchema

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a baccarat (百家樂) 下三路 (derived road) pattern analysis expert.
下三路 = Big Eye Boy (大眼仔), Small Road (小路), Cockroach Pig (蟑螂路).
Each road is a sequence of Red (R) / Blue (B) symbols only.

The user will describe a 下三路 pattern in Chinese or English. Parse it into JSON.

Output STRICT JSON with exactly these fields:
{
  "name": "short Chinese name for this pattern, 2-8 characters",
  "category": "one of: 齊色 | 連龍 | 單跳 | 互補 | 反彈 | custom",
  "canonicalRoads": {
    "bigEye": "a representative R/B string for Big Eye Boy, length 1-12",
    "small": "a representative R/B string for Small Road, length 1-12",
    "cockroach": "a representative R/B string for Cockroach Pig, length 1-12"
  },
  "predictedNext": "B | P  (the outcome this pattern predicts for the NEXT round)",
  "baseConfidence": a float between 0.45 and 0.65 representing how strongly this pattern predicts the next outcome,
  "rationale": "one sentence in Chinese explaining the reasoning"
}

Only output the JSON object, no markdown fences, no extra text.

Example input: 大眼仔小路蟑螂路同時開紅,代表三元及第強訊號
Example output:
{"name": "三元及第", "category": "齊色", "canonicalRoads": {"bigEye": "R", "small": "R", "cockroach": "R"}, "predictedNext": "B", "baseConfidence": 0.60, "rationale": "三路同時開紅代表大路在多個跨度上都呈現對稱,是最強訊號"}
"""


class DerivedNLParseError(RuntimeError):
    pass


def _mock_parse(text: str) -> DerivedNLParseResult:
    """Deterministic fallback parser for offline dev without Azure OpenAI
    credentials."""
    options = [
        ({"bigEye": "R", "small": "R", "cockroach": "R"}, "B"),
        ({"bigEye": "RRRRR", "small": "RRR", "cockroach": "RR"}, "B"),
        ({"bigEye": "RBRBRB", "small": "RBR", "cockroach": "RB"}, "P"),
        ({"bigEye": "BBB", "small": "BB", "cockroach": "B"}, "B"),
    ]
    roads, next_outcome = random.choice(options)
    return DerivedNLParseResult(
        name="自訂下三路",
        category="custom",
        canonicalRoads=DerivedTailSymbolsSchema(**roads),
        predictedNext=next_outcome,
        baseConfidence=0.55,
        rationale=f"(mock parser) 基於輸入文字 '{text[:20]}...' 產生的示意結果",
    )


async def parse_nl_derived_pattern(text: str) -> DerivedNLParseResult:
    settings = get_settings()

    if settings.use_mock_llm:
        return _mock_parse(text)

    if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
        raise DerivedNLParseError(
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
        return DerivedNLParseResult(**data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Azure OpenAI derived NL parse failed")
        raise DerivedNLParseError(f"Failed to parse derived pattern: {exc}") from exc
