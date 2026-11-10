import type { DerivedMatchResult } from "../../api/types";
import { DerivedMatchCard } from "./DerivedMatchCard";

export function DerivedMatchRanking({ match }: { match: DerivedMatchResult | null }) {
  if (!match) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm">
        尚無下三路推薦 — 繼續輸入局數讓大眼仔/小路/蟑螂路開始累積
      </div>
    );
  }

  if (match.noMatch) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm">
        No match (下三路 pattern library 中無匹配)
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-text-muted">
        Round {match.roundNo} · 大眼{" "}
        <span className="font-mono-seq text-text-primary">{match.currentRoads.bigEye || "-"}</span>{" "}
        小路 <span className="font-mono-seq text-text-primary">{match.currentRoads.small || "-"}</span>{" "}
        蟑螂{" "}
        <span className="font-mono-seq text-text-primary">{match.currentRoads.cockroach || "-"}</span>
      </div>
      {match.topMatches[0] && (
        <DerivedMatchCard key={match.topMatches[0].patternId} match={match.topMatches[0]} />
      )}
    </div>
  );
}
