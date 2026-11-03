import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { DerivedEmbedPreviewResponse, DerivedTailSymbolsDto, EmbedPreviewResponse } from "../../api/types";

type Props =
  | { kind: "big"; canonicalSequence: string }
  | { kind: "derived"; canonicalRoads: DerivedTailSymbolsDto };

export function EmbeddingPreview(props: Props) {
  const [preview, setPreview] = useState<EmbedPreviewResponse | DerivedEmbedPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
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
        setPreview(null);
        return;
      }
    } else if (!roadsValid) {
      setPreview(null);
      return;
    }

    const handle = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        if (isBig) {
          const res = await api.patterns.embedPreview(canonicalSequence.toUpperCase());
          setPreview(res);
        } else if (canonicalRoads) {
          const res = await api.derivedPatterns.embedPreview({
            bigEye: canonicalRoads.bigEye.toUpperCase(),
            small: canonicalRoads.small.toUpperCase(),
            cockroach: canonicalRoads.cockroach.toUpperCase(),
          });
          setPreview(res);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }, 400);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isBig, canonicalSequence, canonicalRoads?.bigEye, canonicalRoads?.small, canonicalRoads?.cockroach]);

  if (isBig && !canonicalSequence) return null;
  if (!isBig && !roadsValid) return null;

  return (
    <div className="rounded-lg border border-border-dim bg-bg-deep p-3 space-y-2">
      <div className="text-sm font-semibold text-text-muted">Embedding 預覽(即時)</div>
      {loading && <div className="text-xs text-text-muted">計算中...</div>}
      {error && <div className="text-xs text-banker">{error}</div>}
      {preview && (
        <>
          <div className="text-xs text-text-muted">
            翻譯文本 ({isBig ? "describe_window_in_nl" : "describe_derived_in_nl"}):
          </div>
          <pre className="text-xs font-mono-seq whitespace-pre-wrap bg-bg-card p-2 rounded">
            {preview.textForEmbedding}
          </pre>
          <div className="text-xs text-text-muted">
            Vector (first 16 dims, dim={preview.vectorDim}, L2 norm={preview.vectorNorm}):
          </div>
          <div className="text-xs font-mono-seq break-all text-text-primary/80">
            [{preview.vectorPreview.map((v) => v.toFixed(4)).join(", ")}, ...]
          </div>
        </>
      )}
    </div>
  );
}
