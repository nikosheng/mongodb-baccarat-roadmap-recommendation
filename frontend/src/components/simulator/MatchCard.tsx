import type { PatternMatch } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";
import { ScoreBar } from "../common/ScoreBar";

export function MatchCard({ match }: { match: PatternMatch }) {
  const isTop = !match.lowConfidence;

  return (
    <div
      className={`rounded-lg p-3 border transition ${
        isTop
          ? "border-accent-gold bg-accent-gold/10 shadow-[0_0_12px_rgba(245,158,11,0.3)]"
          : "border-border-dim bg-bg-card"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold">{match.name}</span>
        {match.lowConfidence && (
          <span className="text-xs px-2 py-0.5 rounded bg-border-dim text-text-muted">信心低</span>
        )}
      </div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-text-muted">Score</span>
        <span className="font-mono-seq">{match.score.toFixed(4)}</span>
      </div>
      <ScoreBar score={match.score} highlight={isTop} />
      <div className="flex items-center justify-between mt-2">
        <span className="text-sm text-text-muted">預測下盤</span>
        <div className="flex items-center gap-2">
          <OutcomeBadge outcome={match.predictedNext} size="sm" />
          <span className="text-sm text-text-muted">{(match.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      {match.alsoConsistentWith && match.alsoConsistentWith.length > 0 && (
        <div className="mt-2 text-xs text-text-muted border-t border-border-dim/50 pt-2">
          目前走勢同時符合：{match.alsoConsistentWith.join("、")}（分數非常接近，局數仍不足以明確區分）
        </div>
      )}
    </div>
  );
}
