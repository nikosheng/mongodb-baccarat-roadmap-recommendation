import { Fragment, useState } from "react";
import type { DebugDerivedWindowDetail } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";

export function DerivedDebugView({ detail }: { detail: DebugDerivedWindowDetail | null }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!detail) {
    return <div className="text-text-muted text-sm">載入中...</div>;
  }

  if (detail.insufficientColumns) {
    return (
      <div className="text-text-muted text-sm">
        大路列數還不夠,下三路要等到第 3~4 列才會開始計算
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        <div className="font-semibold text-sm">
          Round {detail.roundNo} 時的下三路符號: 大眼{" "}
          <span className="font-mono-seq ml-1">{detail.tailSymbols?.bigEye || "-"}</span> 小路{" "}
          <span className="font-mono-seq ml-1">{detail.tailSymbols?.small || "-"}</span> 蟑螂{" "}
          <span className="font-mono-seq ml-1">{detail.tailSymbols?.cockroach || "-"}</span>
        </div>

        <div>
          <div className="text-sm text-text-muted mb-1">describe_derived_in_nl 輸出</div>
          <pre className="text-xs font-mono-seq whitespace-pre-wrap bg-bg-deep p-3 rounded">
            {detail.derivedText}
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
        <div className="font-semibold mb-2 text-sm">
          全下三路 Pattern Cosine 排名 (threshold: {detail.threshold ?? "尚未校準"})
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted text-left border-b border-border-dim">
              <th className="py-1">Rank</th>
              <th>Pattern</th>
              <th>Cosine</th>
              <th>Predicts</th>
              <th>BaseConf</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {detail.ranking?.map((r, i) => (
              <Fragment key={r._id}>
                <tr
                  className={`border-b border-border-dim/50 ${
                    detail.threshold != null && r.score >= detail.threshold ? "text-accent-gold" : ""
                  }`}
                >
                  <td className="py-1">{i + 1}</td>
                  <td>{r.name}</td>
                  <td className="font-mono-seq">{r.score.toFixed(4)}</td>
                  <td>
                    <OutcomeBadge outcome={r.predictedNext} size="sm" />
                  </td>
                  <td>{(r.baseConfidence * 100).toFixed(0)}%</td>
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
                    <td colSpan={6} className="bg-bg-deep p-3">
                      <div className="text-xs text-text-muted mb-1">
                        Canonical: 大眼{" "}
                        <span className="font-mono-seq">{r.canonicalRoads.bigEye}</span> 小路{" "}
                        <span className="font-mono-seq">{r.canonicalRoads.small}</span> 蟑螂{" "}
                        <span className="font-mono-seq">{r.canonicalRoads.cockroach}</span>
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
