export type Outcome = "B" | "P" | "T";

export interface ShoeSummary {
  B: number;
  P: number;
  T: number;
}

export interface Shoe {
  shoeId: string;
  tableId: string;
  status: "active" | "closed";
  startedAt: string;
  endedAt: string | null;
  totalRounds: number;
  summary: ShoeSummary;
}

export interface CardDto {
  rank: string;
  suit: string;
}

export type NaturalType = "none" | "banker_natural" | "player_natural" | "both_natural";
export type Lucky6Result = "none" | "banker_6_two_cards" | "banker_6_three_cards";

export interface RoundDoc {
  shoeId: string;
  roundNo: number;
  result: Outcome;
  createdAt: string;
  source: string;

  // Only populated for rounds dealt by the real baccarat dealer
  // (source==="random_sim"); manual B/P/T entries have no card face data.
  bankerCards?: CardDto[] | null;
  playerCards?: CardDto[] | null;
  bankerTotal?: number | null;
  playerTotal?: number | null;
  margin?: number | null;
  bankerCardCount?: number | null;
  playerCardCount?: number | null;
  totalCardCount?: number | null;
  bankerPair?: boolean | null;
  playerPair?: boolean | null;
  bankerPerfectPair?: boolean | null;
  playerPerfectPair?: boolean | null;
  naturalType?: NaturalType | null;
  lucky6Result?: Lucky6Result | null;
}

export interface PatternMatch {
  patternId: string;
  name: string;
  score: number;
  predictedNext: Outcome;
  confidence: number;
  lowConfidence: boolean;
  alsoConsistentWith: string[];
}

export interface MatchResult {
  shoeId: string;
  roundNo: number;
  triggeredAt?: string;
  // Absent when the shoe doesn't have enough rounds yet for a Big Road
  // window match but a derivedMatch (下三路) is still present.
  currentWindow?: string;
  currentWindowText?: string;
  topMatches?: PatternMatch[];
  noMatch?: boolean;
  type?: string;
  derivedMatch?: DerivedMatchResult;
  sideBetMatch?: SideBetMatchResult;
}

export interface Pattern {
  _id: string;
  name: string;
  category: string;
  nlDescription: string;
  canonicalSequence: string;
  minWindowLen: number;
  structuralCategory: string;
  predictedNext: Outcome;
  baseConfidence: number;
  textForEmbedding: string;
  textVersion: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NLParseResult {
  name: string;
  category: string;
  canonicalSequence: string;
  predictedNext: Outcome;
  baseConfidence: number;
  rationale: string;
}

export interface EmbedPreviewResponse {
  textForEmbedding: string;
  vectorPreview: number[];
  vectorDim: number;
  vectorNorm: number;
}

export interface SimilarPatternHit {
  patternId: string;
  name: string;
  score: number;
}

// --------------------------------------------------------------------------
// Derived roads (下三路: Big Eye Boy / Small Road / Cockroach Pig)
// --------------------------------------------------------------------------

export type RoadColor = "R" | "B";

export interface BigRoadCellDto {
  col: number;
  row: number;
  symbol: Outcome;
  tieCount: number;
}

export interface DerivedCellDto {
  col: number;
  row: number;
  color: RoadColor;
}

export interface AllRoads {
  bigRoad: BigRoadCellDto[];
  bigEye: DerivedCellDto[];
  small: DerivedCellDto[];
  cockroach: DerivedCellDto[];
}

export interface DerivedTailSymbolsDto {
  bigEye: string;
  small: string;
  cockroach: string;
}

export type DerivedCategory = "齊色" | "連龍" | "單跳" | "互補" | "反彈" | "custom";

export interface DerivedPattern {
  _id: string;
  name: string;
  category: string;
  nlDescription: string;
  canonicalRoads: DerivedTailSymbolsDto;
  predictedNext: "B" | "P";
  baseConfidence: number;
  textForEmbedding: string;
  textVersion: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface DerivedPatternMatch {
  patternId: string;
  name: string;
  score: number;
  predictedNext: "B" | "P";
  confidence: number;
  lowConfidence: boolean;
}

export interface DerivedMatchResult {
  shoeId: string;
  roundNo: number;
  triggeredAt: string;
  currentRoads: DerivedTailSymbolsDto;
  currentRoadsText: string;
  topMatches: DerivedPatternMatch[];
  noMatch: boolean;
}

export interface DerivedNLParseResult {
  name: string;
  category: string;
  canonicalRoads: DerivedTailSymbolsDto;
  predictedNext: "B" | "P";
  baseConfidence: number;
  rationale: string;
}

export interface DerivedEmbedPreviewResponse {
  textForEmbedding: string;
  vectorPreview: number[];
  vectorDim: number;
  vectorNorm: number;
}

export interface DerivedSimilarPatternHit {
  patternId: string;
  name: string;
  score: number;
}

// --------------------------------------------------------------------------
// Side Bet (Lucky 6 v1, 見 docs/side-bet-lucky6-plan.md)
// --------------------------------------------------------------------------

export type DatasetType = "demo" | "monte_carlo";

export interface SideBetMatchResult {
  shoeId: string;
  sourceRoundNo: number;
  predictionForRoundNo: number;
  triggeredAt: string;

  windowLength: number;
  datasetType: DatasetType;
  insufficientData: boolean;
  reason?: string | null;

  topSimilarityScore?: number | null;
  neighborCount: number;

  lucky6TwoCardHits: number;
  lucky6TwoCardRate?: number | null;
  lucky6TwoCardBaseline?: number | null;
  lucky6TwoCardLift?: number | null;

  lucky6ThreeCardHits: number;
  lucky6ThreeCardRate?: number | null;
  lucky6ThreeCardBaseline?: number | null;
  lucky6ThreeCardLift?: number | null;

  corpusVersion?: string | null;
  featureVersion?: string | null;
}

export interface DebugDerivedWindowDetail {
  shoeId: string;
  roundNo: number;
  insufficientColumns?: boolean;
  tailSymbols?: DerivedTailSymbolsDto;
  derivedText?: string;
  queryVectorPreview?: number[];
  queryVectorNorm?: number;
  threshold?: number | null;
  ranking?: Array<{
    _id: string;
    name: string;
    category: string;
    predictedNext: "B" | "P";
    baseConfidence: number;
    textForEmbedding: string;
    canonicalRoads: DerivedTailSymbolsDto;
    score: number;
  }>;
  gaps?: number[];
}

export interface DebugWindowDetail {
  shoeId: string;
  roundNo: number;
  window: string;
  windowText?: string;
  insufficientRounds?: boolean;
  minWindowForMatch?: number;
  windowStats?: {
    length: number;
    counts: Record<Outcome, number>;
    ratios: Record<Outcome, number>;
    maxStreak: Record<string, number>;
    currentStreakType: string;
    currentStreakLen: number;
    chopCount: number;
    reversal: string | null;
    rhythm: string;
  };
  queryVectorPreview?: number[];
  queryVectorNorm?: number;
  threshold?: number;
  ranking?: Array<{
    _id: string;
    name: string;
    category: string;
    predictedNext: Outcome;
    baseConfidence: number;
    textForEmbedding: string;
    canonicalSequence: string;
    structuralCategory: string;
    eligible: boolean;
    score: number;
  }>;
  gaps?: number[];
}
