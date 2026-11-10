import type { SideBetMatchResult } from "../../api/types";

function pct(v: number | null | undefined): string {
  if (v == null) return "-";
  return `${(v * 100).toFixed(2)}%`;
}

function liftLabel(v: number | null | undefined): string {
  if (v == null) return "樣本不足";
  return `${v.toFixed(1)}x`;
}

/** Shows the next-hand Lucky 6 exploratory statistics for the most similar
 * historical windows (Top K vector-search neighbors). This is an
 * observational similarity-search result over synthetic Monte Carlo /
 * demo data, not a calibrated probability — the copy here deliberately
 * avoids phrases like "機率飆升" and always surfaces n/hits alongside any
 * rate (see docs/side-bet-lucky6-plan.md §7, §9). */
export function SideBetPanel({ match }: { match: SideBetMatchResult | null }) {
  if (!match) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm">
        尚無 Side Bet 統計 — 持續隨機發牌,累積滿 N 手含牌面的連續局後開始顯示
      </div>
    );
  }

  if (match.insufficientData) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-4 text-text-muted text-sm space-y-1">
        <div>Side Bet(Lucky 6)資料不足</div>
        {match.reason && <div className="text-xs">{match.reason}</div>}
      </div>
    );
  }

  const datasetLabel = match.datasetType === "demo" ? "Demo fixture" : "Monte Carlo 合成語料";

  return (
    <div className="rounded-lg border border-border-dim bg-bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">
          下一手(Round {match.predictionForRoundNo})Lucky 6 探索性統計
        </span>
        <span className="text-xs px-2 py-0.5 rounded bg-border-dim text-text-muted">
          N={match.windowLength} · {datasetLabel}
        </span>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-text-muted">最相似歷史窗口 Atlas 相似度分數</span>
        <span className="font-mono-seq text-accent-gold">
          {match.topSimilarityScore != null ? match.topSimilarityScore.toFixed(4) : "-"}
        </span>
      </div>

      <div className="text-xs text-text-muted">
        相似窗口樣本:{match.neighborCount} 個不同歷史靴
        {match.reason && <span className="ml-1">({match.reason})</span>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-border-dim p-2 space-y-1">
          <div className="text-xs text-text-muted">莊家兩張 6 點勝</div>
          <div className="text-sm font-mono-seq">
            {match.lucky6TwoCardHits}/{match.neighborCount}({pct(match.lucky6TwoCardRate)})
          </div>
          <div className="text-xs text-text-muted">
            baseline {pct(match.lucky6TwoCardBaseline)} · lift{" "}
            <span className="text-text-primary font-semibold">{liftLabel(match.lucky6TwoCardLift)}</span>
          </div>
        </div>
        <div className="rounded-md border border-border-dim p-2 space-y-1">
          <div className="text-xs text-text-muted">莊家三張 6 點勝</div>
          <div className="text-sm font-mono-seq">
            {match.lucky6ThreeCardHits}/{match.neighborCount}({pct(match.lucky6ThreeCardRate)})
          </div>
          <div className="text-xs text-text-muted">
            baseline {pct(match.lucky6ThreeCardBaseline)} · lift{" "}
            <span className="text-text-primary font-semibold">{liftLabel(match.lucky6ThreeCardLift)}</span>
          </div>
        </div>
      </div>

      <div className="text-xs text-text-muted border-t border-border-dim pt-2">
        n={match.neighborCount} 樣本很少,波動會很大;以上為合成資料的探索性統計,不代表真實投注優勢。
      </div>
    </div>
  );
}
