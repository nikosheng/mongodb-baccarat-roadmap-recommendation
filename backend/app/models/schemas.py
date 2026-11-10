"""Pydantic schemas for API request/response and Mongo document shapes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Outcome = Literal["B", "P", "T"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Shoes / Rounds
# --------------------------------------------------------------------------

class ShoeSummary(BaseModel):
    B: int = 0
    P: int = 0
    T: int = 0


class Shoe(BaseModel):
    shoeId: str
    tableId: str = "DEMO_T1"
    status: Literal["active", "closed"] = "active"
    startedAt: datetime = Field(default_factory=utcnow)
    endedAt: Optional[datetime] = None
    totalRounds: int = 0
    summary: ShoeSummary = Field(default_factory=ShoeSummary)


class Card(BaseModel):
    rank: str
    suit: str


NaturalType = Literal["none", "banker_natural", "player_natural", "both_natural"]
Lucky6Result = Literal["none", "banker_6_two_cards", "banker_6_three_cards"]


class Round(BaseModel):
    shoeId: str
    roundNo: int
    result: Outcome
    createdAt: datetime = Field(default_factory=utcnow)
    source: str = "manual_sim"

    # Card-face data: only populated for rounds dealt by the real baccarat
    # dealer (source="random_sim"). Manual B/P/T entries (source="manual_sim")
    # have no card face, so these all stay None — they must never be used as
    # Side Bet feature inputs (see docs/side-bet-lucky6-plan.md §3.2).
    bankerCards: Optional[list[Card]] = None
    playerCards: Optional[list[Card]] = None
    bankerTotal: Optional[int] = None
    playerTotal: Optional[int] = None
    margin: Optional[int] = None  # bankerTotal - playerTotal, range -9..9; 0 for Tie
    bankerCardCount: Optional[int] = None
    playerCardCount: Optional[int] = None
    totalCardCount: Optional[int] = None
    bankerPair: Optional[bool] = None
    playerPair: Optional[bool] = None
    bankerPerfectPair: Optional[bool] = None
    playerPerfectPair: Optional[bool] = None
    naturalType: Optional[NaturalType] = None
    lucky6Result: Optional[Lucky6Result] = None


class RoundCreateRequest(BaseModel):
    result: Outcome


class RandomizeRequest(BaseModel):
    n: int = Field(default=1, ge=1, le=80)


# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

class PatternCreateRequest(BaseModel):
    name: str
    category: str = "custom"
    nlDescription: str
    canonicalSequence: str  # e.g. "BBBBBBP"
    predictedNext: Outcome
    baseConfidence: float = Field(ge=0.0, le=1.0, default=0.55)
    enabled: bool = True


class PatternUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    nlDescription: Optional[str] = None
    canonicalSequence: Optional[str] = None
    predictedNext: Optional[Outcome] = None
    baseConfidence: Optional[float] = None
    enabled: Optional[bool] = None


class Pattern(BaseModel):
    id: str = Field(alias="_id")
    name: str
    category: str
    nlDescription: str
    canonicalSequence: str
    minWindowLen: int
    structuralCategory: str
    predictedNext: Outcome
    baseConfidence: float
    textForEmbedding: str
    textVersion: str
    enabled: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = {"populate_by_name": True}


class NLParseRequest(BaseModel):
    text: str


class NLParseResult(BaseModel):
    name: str
    category: str
    canonicalSequence: str
    predictedNext: Outcome
    baseConfidence: float
    rationale: str = ""


class EmbedPreviewRequest(BaseModel):
    canonicalSequence: str


class EmbedPreviewResponse(BaseModel):
    textForEmbedding: str
    vectorPreview: list[float]
    vectorDim: int
    vectorNorm: float


class SimilarityCheckRequest(BaseModel):
    canonicalSequence: str
    excludePatternId: Optional[str] = None


class SimilarPatternHit(BaseModel):
    patternId: str
    name: str
    score: float


class SimilarityCheckResponse(BaseModel):
    hits: list[SimilarPatternHit]


# --------------------------------------------------------------------------
# Matches
# --------------------------------------------------------------------------

class PatternMatch(BaseModel):
    patternId: str
    name: str
    score: float
    predictedNext: Outcome
    confidence: float
    lowConfidence: bool = False
    alsoConsistentWith: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    shoeId: str
    roundNo: int
    triggeredAt: datetime = Field(default_factory=utcnow)
    currentWindow: str
    currentWindowText: str
    topMatches: list[PatternMatch]
    noMatch: bool = False


# --------------------------------------------------------------------------
# Derived roads (下三路: Big Eye Boy / Small Road / Cockroach Pig)
# --------------------------------------------------------------------------

RoadColor = Literal["R", "B"]


class BigRoadCellSchema(BaseModel):
    col: int
    row: int
    symbol: str  # "B" | "P" | "T" (T only when a shoe has no B/P result)
    tieCount: int = 0


class DerivedCellSchema(BaseModel):
    col: int
    row: int
    color: RoadColor


class AllRoads(BaseModel):
    bigRoad: list[BigRoadCellSchema]
    bigEye: list[DerivedCellSchema]
    small: list[DerivedCellSchema]
    cockroach: list[DerivedCellSchema]


class DerivedTailSymbolsSchema(BaseModel):
    bigEye: str
    small: str
    cockroach: str


# --------------------------------------------------------------------------
# Derived Patterns (下三路 pattern library)
# --------------------------------------------------------------------------

DerivedCategory = Literal["齊色", "連龍", "單跳", "互補", "反彈", "custom"]


class DerivedPatternCreateRequest(BaseModel):
    name: str
    category: DerivedCategory = "custom"
    nlDescription: str
    canonicalRoads: DerivedTailSymbolsSchema
    predictedNext: Literal["B", "P"]
    baseConfidence: float = Field(ge=0.0, le=1.0, default=0.55)
    enabled: bool = True


class DerivedPatternUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[DerivedCategory] = None
    nlDescription: Optional[str] = None
    canonicalRoads: Optional[DerivedTailSymbolsSchema] = None
    predictedNext: Optional[Literal["B", "P"]] = None
    baseConfidence: Optional[float] = None
    enabled: Optional[bool] = None


class DerivedPattern(BaseModel):
    id: str = Field(alias="_id")
    name: str
    category: str
    nlDescription: str
    canonicalRoads: DerivedTailSymbolsSchema
    predictedNext: Literal["B", "P"]
    baseConfidence: float
    textForEmbedding: str
    textVersion: str
    enabled: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = {"populate_by_name": True}


class DerivedNLParseRequest(BaseModel):
    text: str


class DerivedNLParseResult(BaseModel):
    name: str
    category: str
    canonicalRoads: DerivedTailSymbolsSchema
    predictedNext: Literal["B", "P"]
    baseConfidence: float
    rationale: str = ""


class DerivedEmbedPreviewRequest(BaseModel):
    canonicalRoads: DerivedTailSymbolsSchema


class DerivedEmbedPreviewResponse(BaseModel):
    textForEmbedding: str
    vectorPreview: list[float]
    vectorDim: int
    vectorNorm: float


class DerivedSimilarityCheckRequest(BaseModel):
    canonicalRoads: DerivedTailSymbolsSchema
    excludePatternId: Optional[str] = None


class DerivedSimilarPatternHit(BaseModel):
    patternId: str
    name: str
    score: float


class DerivedSimilarityCheckResponse(BaseModel):
    hits: list[DerivedSimilarPatternHit]


# --------------------------------------------------------------------------
# Derived Matches
# --------------------------------------------------------------------------

class DerivedPatternMatch(BaseModel):
    patternId: str
    name: str
    score: float
    predictedNext: Literal["B", "P"]
    confidence: float
    lowConfidence: bool = False


class DerivedMatchResult(BaseModel):
    shoeId: str
    roundNo: int
    triggeredAt: datetime = Field(default_factory=utcnow)
    currentRoads: DerivedTailSymbolsSchema
    currentRoadsText: str
    topMatches: list[DerivedPatternMatch]
    noMatch: bool = False


# --------------------------------------------------------------------------
# Side Bet (Lucky 6 v1) — see docs/side-bet-lucky6-plan.md
# --------------------------------------------------------------------------

DatasetType = Literal["demo", "monte_carlo"]


class SideBetMatchResult(BaseModel):
    shoeId: str
    sourceRoundNo: int
    predictionForRoundNo: int
    triggeredAt: datetime = Field(default_factory=utcnow)

    windowLength: int
    datasetType: DatasetType
    insufficientData: bool = False
    reason: Optional[str] = None

    topSimilarityScore: Optional[float] = None
    neighborCount: int = 0

    lucky6TwoCardHits: int = 0
    lucky6TwoCardRate: Optional[float] = None
    lucky6TwoCardBaseline: Optional[float] = None
    lucky6TwoCardLift: Optional[float] = None

    lucky6ThreeCardHits: int = 0
    lucky6ThreeCardRate: Optional[float] = None
    lucky6ThreeCardBaseline: Optional[float] = None
    lucky6ThreeCardLift: Optional[float] = None

    corpusVersion: Optional[str] = None
    featureVersion: Optional[str] = None
