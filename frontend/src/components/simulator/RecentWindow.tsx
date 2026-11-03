import type { RoundDoc } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";

export function RecentWindow({ rounds, maxWindow = 10 }: { rounds: RoundDoc[]; maxWindow?: number }) {
  const recent = rounds.slice(-maxWindow);
  return (
    <div>
      <div className="text-sm text-text-muted mb-1">
        最近 {recent.length} 局(window ≤ {maxWindow})
      </div>
      <div className="flex gap-1 flex-wrap">
        {recent.map((r) => (
          <OutcomeBadge key={r.roundNo} outcome={r.result} size="sm" />
        ))}
        {recent.length === 0 && <span className="text-text-muted text-sm">尚無局數</span>}
      </div>
    </div>
  );
}
