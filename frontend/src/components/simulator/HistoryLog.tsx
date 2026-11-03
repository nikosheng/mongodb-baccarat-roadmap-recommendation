import type { MatchResult, RoundDoc } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";

export function HistoryLog({ history, rounds }: { history: MatchResult[]; rounds: RoundDoc[] }) {
  const recent = history.slice(0, 5);

  function actualOutcomeFor(roundNo: number) {
    // The match for round N predicts round N+1's outcome
    return rounds.find((r) => r.roundNo === roundNo + 1)?.result ?? null;
  }

  return (
    <div className="rounded-lg border border-border-dim bg-bg-card p-3">
      <div className="text-sm font-semibold mb-2">📋 最近 5 次推薦紀錄</div>
      <div className="space-y-1">
        {recent.length === 0 && <div className="text-text-muted text-sm">尚無紀錄</div>}
        {recent.map((m) => {
          if (m.noMatch || !m.topMatches || m.topMatches.length === 0) return null;
          const top = m.topMatches[0];
          const actual = actualOutcomeFor(m.roundNo);
          const correct = actual ? actual === top.predictedNext : null;
          return (
            <div key={m.roundNo} className="flex items-center justify-between text-sm">
              <span className="text-text-muted">R{m.roundNo}</span>
              <span>{top.name}</span>
              <span className="flex items-center gap-1">
                {actual ? (
                  <>
                    <OutcomeBadge outcome={actual} size="sm" />
                    <span>{correct ? "✓" : "✗"}</span>
                  </>
                ) : (
                  <span className="text-text-muted">待定</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
