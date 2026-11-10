import { Fragment, useState } from "react";
import type { DebugWindowDetail } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";

const CATEGORY_LABELS: Record<string, string> = {
  continuous_run: "連續不斷",
  break_resume: "斷後回頭",
  break_end: "斷龍終止",
  chop: "跳動",
  complex: "未分類(複雜)",
};

function categoryLabel(cat: string | undefined): string {
  if (!cat) return "未知";
  return CATEGORY_LABELS[cat] ?? cat;
}

export function BigRoadDebugView({ detail }: { detail: DebugWindowDetail | null }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!detail) {
    return <div className="text-text-muted text-sm">載入中...</div>;
  }

  if (detail.insufficientRounds) {
    return (
      <div className="text-text-muted text-sm">
        局數不足(需至少 {detail.minWindowForMatch} 局才會計算匹配)
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div className="font-semibold text-sm">
          Round {detail.roundNo} 時的 window:
          <span className="font-mono-seq ml-2">{detail.window}</span>
        </div>

        <div>
          <div className="text-sm text-text-muted mb-1">describe_window_in_nl 輸出</div>
          <pre className="text-xs font-mono-seq whitespace-pre-wrap bg-bg-deep p-3 rounded">
            {detail.windowText}
          </pre>
        </div>

        <div>
          <div className="text-sm text-text-muted mb-1">
            Query Vector (前 16 維,L2 Norm: {detail.queryVectorNorm})
          </div>
          <div className="text-xs font-mono-seq break-all bg-bg-deep p-3 rounded">
            [{detail.queryVectorPreview?.map((v) => v.toFixed(4)).join(", ")}, ...]
          </div>
        </div>
      </div>

      <div>
        <div className="font-semibold mb-1 text-sm">
          全 Pattern Cosine 排名 (threshold: {detail.threshold})
        </div>
        <div className="text-xs text-text-muted mb-2">
          這是未套用結構過濾的原始相似度排名。帶 ❌ 標記的候選分數可能很高，但目前窗口的走勢結構
          已經不符合該 Pattern 的敘事分類（例如已經出現打斷、或段數已經超過該分類允許的範圍），
          因此<strong className="text-text-primary">不會</strong>出現在正式推薦中。
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted text-left border-b border-border-dim">
              <th className="py-1">Rank</th>
              <th>Pattern</th>
              <th>Cosine</th>
              <th>Predicts</th>
              <th>BaseConf</th>
              <th>資格</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {detail.ranking?.map((r, i) => (
              <Fragment key={r._id}>
                <tr
                  className={`border-b border-border-dim/50 ${
                    !r.eligible
                      ? "opacity-40"
                      : r.score >= (detail.threshold ?? 0.82)
                        ? "text-accent-gold"
                        : ""
                  }`}
                >
                  <td className="py-1">{i + 1}</td>
                  <td className={!r.eligible ? "line-through" : ""}>{r.name}</td>
                  <td className="font-mono-seq">{r.score.toFixed(4)}</td>
                  <td>
                    <OutcomeBadge outcome={r.predictedNext} size="sm" />
                  </td>
                  <td>{(r.baseConfidence * 100).toFixed(0)}%</td>
                  <td>
                    {r.eligible ? (
                      <span className="text-xs text-text-muted" title={categoryLabel(r.structuralCategory)}>
                        ✅ {categoryLabel(r.structuralCategory)}
                      </span>
                    ) : (
                      <span
                        className="text-xs text-banker"
                        title="窗口目前的走勢結構已經排除這個分類,此 Pattern 不會出現在正式推薦中"
                      >
                        ❌ {categoryLabel(r.structuralCategory)}已排除
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      onClick={() => setExpandedId(expandedId === r._id ? null : r._id)}
                      className="text-xs underline text-player"
                    >
                      {expandedId === r._id ? "收合" : "看文本"}
                    </button>
                  </td>
                </tr>
                {expandedId === r._id && (
                  <tr>
                    <td colSpan={7} className="bg-bg-deep p-3">
                      <div className="text-xs text-text-muted mb-1">
                        Canonical: <span className="font-mono-seq">{r.canonicalSequence}</span>
                        {" · "}structuralCategory: {categoryLabel(r.structuralCategory)}
                        {!r.eligible && (
                          <span className="text-banker">
                            {" "}
                            (窗口走勢結構不符,此候選已從正式推薦排除)
                          </span>
                        )}
                      </div>
                      <pre className="text-xs font-mono-seq whitespace-pre-wrap">{r.textForEmbedding}</pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        {detail.gaps && detail.gaps.length > 0 && (
          <div className="text-xs text-text-muted mt-2">
            Gap top1-top2: {detail.gaps[0]?.toFixed(4)} &nbsp; Gap top2-top3: {detail.gaps[1]?.toFixed(4)}
          </div>
        )}
      </div>
    </div>
  );
}
