import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { DebugDerivedWindowDetail, DebugWindowDetail, RoundDoc, Shoe } from "../../api/types";
import { useAppStore } from "../../stores/useAppStore";
import { BigRoadDebugView } from "../debug/BigRoadDebugView";
import { DerivedDebugView } from "../debug/DerivedDebugView";

export function DebugInspector({ shoe, rounds }: { shoe: Shoe | null; rounds: RoundDoc[] }) {
  const debugExpanded = useAppStore((s) => s.debugExpanded);
  const setDebugExpanded = useAppStore((s) => s.setDebugExpanded);

  const [roundNo, setRoundNo] = useState<number | null>(null);
  const [tab, setTab] = useState<"big" | "derived">("big");
  const [bigDetail, setBigDetail] = useState<DebugWindowDetail | null>(null);
  const [derivedDetail, setDerivedDetail] = useState<DebugDerivedWindowDetail | null>(null);

  // Keep the round selector pinned to the latest round unless the user has
  // manually picked an earlier one.
  useEffect(() => {
    if (rounds.length === 0) {
      setRoundNo(null);
      return;
    }
    setRoundNo(rounds[rounds.length - 1].roundNo);
  }, [rounds.length]);

  useEffect(() => {
    if (!debugExpanded || !shoe || roundNo === null) return;
    api.debug
      .windowDetail(shoe.shoeId, roundNo)
      .then(setBigDetail)
      .catch(() => setBigDetail(null));
    api.debug
      .derivedWindowDetail(shoe.shoeId, roundNo)
      .then(setDerivedDetail)
      .catch(() => setDerivedDetail(null));
  }, [debugExpanded, shoe, roundNo]);

  // Keyboard shortcut: "d" toggles the inspector open/closed.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "d" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = e.target as HTMLElement | null;
        if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
        setDebugExpanded(!debugExpanded);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [debugExpanded, setDebugExpanded]);

  if (!shoe) return null;

  return (
    <details
      className="rounded-lg border border-border-dim bg-bg-card p-4"
      open={debugExpanded}
      onToggle={(e) => setDebugExpanded((e.target as HTMLDetailsElement).open)}
    >
      <summary className="text-sm font-semibold cursor-pointer select-none">
        🔍 Debug Inspector(展開看詳細排序與向量,快捷鍵 d) — Round {roundNo ?? "-"}
      </summary>

      {debugExpanded && (
        <div className="mt-4 space-y-4">
          <div className="flex items-center gap-2">
            <button
              disabled={roundNo === null || roundNo <= 1}
              onClick={() => setRoundNo((n) => (n ? n - 1 : n))}
              className="px-2 py-1 rounded bg-bg-deep border border-border-dim text-sm disabled:opacity-40"
            >
              ← 上一局
            </button>
            <select
              value={roundNo ?? ""}
              onChange={(e) => setRoundNo(Number(e.target.value))}
              className="px-2 py-1 rounded bg-bg-deep border border-border-dim text-sm"
            >
              {rounds.map((r) => (
                <option key={r.roundNo} value={r.roundNo}>
                  Round {r.roundNo}
                </option>
              ))}
            </select>
            <button
              disabled={roundNo === null || roundNo >= rounds.length}
              onClick={() => setRoundNo((n) => (n ? n + 1 : n))}
              className="px-2 py-1 rounded bg-bg-deep border border-border-dim text-sm disabled:opacity-40"
            >
              下一局 →
            </button>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setTab("big")}
              className={`px-3 py-1.5 rounded-md text-sm ${
                tab === "big" ? "bg-accent-gold text-bg-deep" : "bg-bg-deep text-text-muted"
              }`}
            >
              大路 Debug
            </button>
            <button
              onClick={() => setTab("derived")}
              className={`px-3 py-1.5 rounded-md text-sm ${
                tab === "derived" ? "bg-accent-gold text-bg-deep" : "bg-bg-deep text-text-muted"
              }`}
            >
              下三路 Debug
            </button>
          </div>

          {tab === "big" ? <BigRoadDebugView detail={bigDetail} /> : <DerivedDebugView detail={derivedDetail} />}
        </div>
      )}
    </details>
  );
}
