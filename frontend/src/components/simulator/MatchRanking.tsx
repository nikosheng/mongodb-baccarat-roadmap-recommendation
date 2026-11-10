import type { MatchResult } from "../../api/types";
import { MatchCard } from "./MatchCard";

export function MatchRanking({ match }: { match: MatchResult | null }) {
  if (!match) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm">
        尚無推薦 — 繼續輸入局數以累積 window
      </div>
    );
  }

  if (match.noMatch || !match.topMatches) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm">
        No match (threshold not reached)
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-text-muted">
        Round {match.roundNo} · window:{" "}
        <span className="font-mono-seq text-text-primary">{match.currentWindow}</span>
      </div>
      {match.topMatches[0] && <MatchCard key={match.topMatches[0].patternId} match={match.topMatches[0]} />}
    </div>
  );
}
