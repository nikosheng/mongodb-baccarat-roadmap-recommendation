import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { DerivedTailSymbolsDto, SimilarPatternHit } from "../../api/types";

type Props =
  | { kind: "big"; canonicalSequence: string; excludePatternId?: string }
  | { kind: "derived"; canonicalRoads: DerivedTailSymbolsDto; excludePatternId?: string };

export function SimilarityCheck(props: Props) {
  const [hits, setHits] = useState<SimilarPatternHit[] | null>(null);
  const [loading, setLoading] = useState(false);

  const isBig = props.kind === "big";
  const canonicalSequence = isBig ? props.canonicalSequence : "";
  const canonicalRoads = !isBig ? props.canonicalRoads : null;
  const roadsValid =
    canonicalRoads &&
    [canonicalRoads.bigEye, canonicalRoads.small, canonicalRoads.cockroach].some(
      (v) => v && /^[RB]+$/i.test(v)
    );

  useEffect(() => {
    if (isBig) {
      if (!canonicalSequence || !/^[BPT]+$/i.test(canonicalSequence)) {
        setHits(null);
        return;
      }
    } else if (!roadsValid) {
      setHits(null);
      return;
    }

    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        if (isBig) {
          const res = await api.patterns.similarityCheck(canonicalSequence.toUpperCase(), props.excludePatternId);
          setHits(res.hits);
        } else if (canonicalRoads) {
          const res = await api.derivedPatterns.similarityCheck(
            {
              bigEye: canonicalRoads.bigEye.toUpperCase(),
              small: canonicalRoads.small.toUpperCase(),
              cockroach: canonicalRoads.cockroach.toUpperCase(),
            },
            props.excludePatternId
          );
          setHits(res.hits);
        }
      } catch {
        setHits(null);
      } finally {
        setLoading(false);
      }
    }, 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isBig,
    canonicalSequence,
    canonicalRoads?.bigEye,
    canonicalRoads?.small,
    canonicalRoads?.cockroach,
    props.excludePatternId,
  ]);

  if (isBig && !canonicalSequence) return null;
  if (!isBig && !roadsValid) return null;

  return (
    <div className="rounded-lg border border-border-dim bg-bg-deep p-3 space-y-1">
      <div className="text-sm font-semibold text-text-muted">現有 Pattern 相似度(語義去重檢查)</div>
      {loading && <div className="text-xs text-text-muted">檢查中...</div>}
      {hits && hits.length === 0 && (
        <div className="text-xs text-green-400">✓ 與現有 pattern 差異明顯,可安全加入</div>
      )}
      {hits &&
        hits.slice(0, 5).map((h) => (
          <div key={h.patternId} className="text-xs flex items-center gap-2">
            <span className={h.score >= 0.8 ? "text-accent-gold" : "text-text-muted"}>
              {h.score >= 0.8 ? "⚠️" : "✓"}
            </span>
            <span>與「{h.name}」相似度 {h.score.toFixed(2)}</span>
          </div>
        ))}
    </div>
  );
}
