import type {
  AllRoads,
  DebugDerivedWindowDetail,
  DebugWindowDetail,
  DerivedEmbedPreviewResponse,
  DerivedMatchResult,
  DerivedNLParseResult,
  DerivedPattern,
  DerivedSimilarPatternHit,
  DerivedTailSymbolsDto,
  EmbedPreviewResponse,
  MatchResult,
  NLParseResult,
  Outcome,
  Pattern,
  RoundDoc,
  Shoe,
  SideBetMatchResult,
  SimilarPatternHit,
} from "./types";

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  shoes: {
    create: (tableId = "DEMO_T1") =>
      request<Shoe>(`/api/shoes?table_id=${encodeURIComponent(tableId)}`, {
        method: "POST",
      }),
    get: (id: string) => request<Shoe>(`/api/shoes/${id}`),
    close: (id: string) => request<Shoe>(`/api/shoes/${id}/close`, { method: "POST" }),
    getRounds: (id: string) => request<RoundDoc[]>(`/api/shoes/${id}/rounds`),
    addRound: (id: string, result: Outcome) =>
      request<{ round: RoundDoc; match: MatchResult | null }>(
        `/api/shoes/${id}/rounds`,
        { method: "POST", body: JSON.stringify({ result }) }
      ),
    randomize: (id: string, n: number) =>
      request<{ rounds: RoundDoc[]; lastMatch: MatchResult | null; pastCutCard: boolean }>(
        `/api/shoes/${id}/randomize`,
        { method: "POST", body: JSON.stringify({ n }) }
      ),
    getMatches: (id: string, limit = 50) =>
      request<MatchResult[]>(`/api/shoes/${id}/matches?limit=${limit}`),
    getRoads: (id: string) => request<AllRoads>(`/api/shoes/${id}/roads`),
    getDerivedMatches: (id: string, limit = 50) =>
      request<DerivedMatchResult[]>(`/api/shoes/${id}/derived-matches?limit=${limit}`),
    getSideBetMatches: (id: string, limit = 50) =>
      request<SideBetMatchResult[]>(`/api/shoes/${id}/side-bet-matches?limit=${limit}`),
  },
  patterns: {
    list: (params?: { category?: string; enabled?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.category) qs.set("category", params.category);
      if (params?.enabled !== undefined) qs.set("enabled", String(params.enabled));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return request<Pattern[]>(`/api/patterns${suffix}`);
    },
    get: (id: string) => request<Pattern>(`/api/patterns/${id}`),
    create: (body: {
      name: string;
      category: string;
      nlDescription: string;
      canonicalSequence: string;
      predictedNext: Outcome;
      baseConfidence: number;
      enabled?: boolean;
    }) =>
      request<Pattern>(`/api/patterns`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    update: (id: string, body: Partial<Pattern>) =>
      request<Pattern>(`/api/patterns/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      request<{ deleted: boolean }>(`/api/patterns/${id}`, { method: "DELETE" }),
    parseNL: (text: string) =>
      request<NLParseResult>(`/api/patterns/nl`, {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    embedPreview: (canonicalSequence: string) =>
      request<EmbedPreviewResponse>(`/api/patterns/embed-preview`, {
        method: "POST",
        body: JSON.stringify({ canonicalSequence }),
      }),
    similarityCheck: (canonicalSequence: string, excludePatternId?: string) =>
      request<{ hits: SimilarPatternHit[] }>(`/api/patterns/similarity-check`, {
        method: "POST",
        body: JSON.stringify({ canonicalSequence, excludePatternId }),
      }),
  },
  derivedPatterns: {
    list: (params?: { category?: string; enabled?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.category) qs.set("category", params.category);
      if (params?.enabled !== undefined) qs.set("enabled", String(params.enabled));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return request<DerivedPattern[]>(`/api/derived-patterns${suffix}`);
    },
    get: (id: string) => request<DerivedPattern>(`/api/derived-patterns/${id}`),
    create: (body: {
      name: string;
      category: string;
      nlDescription: string;
      canonicalRoads: DerivedTailSymbolsDto;
      predictedNext: "B" | "P";
      baseConfidence: number;
      enabled?: boolean;
    }) =>
      request<DerivedPattern>(`/api/derived-patterns`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    update: (id: string, body: Partial<DerivedPattern>) =>
      request<DerivedPattern>(`/api/derived-patterns/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      request<{ deleted: boolean }>(`/api/derived-patterns/${id}`, { method: "DELETE" }),
    parseNL: (text: string) =>
      request<DerivedNLParseResult>(`/api/derived-patterns/nl`, {
        method: "POST",
        body: JSON.stringify({ text }),
      }),
    embedPreview: (canonicalRoads: DerivedTailSymbolsDto) =>
      request<DerivedEmbedPreviewResponse>(`/api/derived-patterns/embed-preview`, {
        method: "POST",
        body: JSON.stringify({ canonicalRoads }),
      }),
    similarityCheck: (canonicalRoads: DerivedTailSymbolsDto, excludePatternId?: string) =>
      request<{ hits: DerivedSimilarPatternHit[] }>(`/api/derived-patterns/similarity-check`, {
        method: "POST",
        body: JSON.stringify({ canonicalRoads, excludePatternId }),
      }),
  },
  debug: {
    windowDetail: (shoeId: string, roundNo: number) =>
      request<DebugWindowDetail>(`/api/debug/windows/${shoeId}/${roundNo}`),
    derivedWindowDetail: (shoeId: string, roundNo: number) =>
      request<DebugDerivedWindowDetail>(`/api/debug/derived/${shoeId}/${roundNo}`),
  },
};
