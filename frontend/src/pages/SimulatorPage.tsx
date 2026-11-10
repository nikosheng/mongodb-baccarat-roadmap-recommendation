import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Outcome } from "../api/types";
import { BigRoad } from "../components/simulator/BigRoad";
import { DerivedRoadsPanel } from "../components/simulator/DerivedRoadsPanel";
import { RecentWindow } from "../components/simulator/RecentWindow";
import { RoundInputPanel } from "../components/simulator/RoundInputPanel";
import { MatchRanking } from "../components/simulator/MatchRanking";
import { DerivedMatchRanking } from "../components/simulator/DerivedMatchRanking";
import { SideBetPanel } from "../components/simulator/SideBetPanel";
import { CardFaceDisplay } from "../components/simulator/CardFaceDisplay";
import { HistoryLog } from "../components/simulator/HistoryLog";
import { ShoeHeader } from "../components/simulator/ShoeHeader";
import { ConnectionStatus } from "../components/common/ConnectionDot";
import { DebugInspector } from "../components/simulator/DebugInspector";
import { LongDragonAnimation } from "../components/simulator/LongDragonAnimation";
import { useTableWebSocket } from "../hooks/useWebSocket";
import { useLongDragonTrigger } from "../hooks/useLongDragonTrigger";
import { useAppStore } from "../stores/useAppStore";

export function SimulatorPage() {
  const [loading, setLoading] = useState(false);
  const currentShoe = useAppStore((s) => s.currentShoe);
  const rounds = useAppStore((s) => s.rounds);
  const latestMatch = useAppStore((s) => s.latestMatch);
  const matchHistory = useAppStore((s) => s.matchHistory);
  const latestDerivedMatch = useAppStore((s) => s.latestDerivedMatch);
  const latestSideBetMatch = useAppStore((s) => s.latestSideBetMatch);
  const setShoe = useAppStore((s) => s.setShoe);
  const setRounds = useAppStore((s) => s.setRounds);
  const addRoundLocal = useAppStore((s) => s.addRoundLocal);
  const pushMatch = useAppStore((s) => s.pushMatch);
  const pushDerivedMatch = useAppStore((s) => s.pushDerivedMatch);
  const pushSideBetMatch = useAppStore((s) => s.pushSideBetMatch);
  const resetShoe = useAppStore((s) => s.resetShoe);

  useTableWebSocket(currentShoe?.tableId ?? null);
  const dragonKey = useLongDragonTrigger();

  const startNewShoe = useCallback(async () => {
    setLoading(true);
    try {
      const shoe = await api.shoes.create("DEMO_T1");
      resetShoe();
      setShoe(shoe);
      setRounds([]);
    } finally {
      setLoading(false);
    }
  }, [resetShoe, setShoe, setRounds]);

  // Guard against React 18 StrictMode's dev-only double-invocation of the
  // initial mount effect, which would otherwise race-create two shoes.
  const didInitRef = useRef(false);
  useEffect(() => {
    if (didInitRef.current) return;
    didInitRef.current = true;
    startNewShoe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleInput(result: Outcome) {
    if (!currentShoe) return;
    setLoading(true);
    try {
      const { round, match } = await api.shoes.addRound(currentShoe.shoeId, result);
      addRoundLocal(round);
      const updated = await api.shoes.get(currentShoe.shoeId);
      setShoe(updated);
      if (match) {
        if (match.topMatches !== undefined || match.noMatch !== undefined) {
          pushMatch({ ...match, type: "match" });
        }
        if (match.derivedMatch) pushDerivedMatch(match.derivedMatch);
        if (match.sideBetMatch) pushSideBetMatch(match.sideBetMatch);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRandomize(n: number) {
    if (!currentShoe) return;
    setLoading(true);
    try {
      const { rounds: newRounds, lastMatch } = await api.shoes.randomize(currentShoe.shoeId, n);
      for (const r of newRounds) addRoundLocal(r);
      const updated = await api.shoes.get(currentShoe.shoeId);
      setShoe(updated);
      if (lastMatch) {
        if (lastMatch.topMatches !== undefined || lastMatch.noMatch !== undefined) {
          pushMatch({ ...lastMatch, type: "match" });
        }
        if (lastMatch.derivedMatch) pushDerivedMatch(lastMatch.derivedMatch);
        if (lastMatch.sideBetMatch) pushSideBetMatch(lastMatch.sideBetMatch);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {dragonKey && <LongDragonAnimation key={dragonKey} />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="rounded-lg border border-border-dim bg-bg-card p-4 space-y-4">
            <ShoeHeader shoe={currentShoe} />
            <BigRoad rounds={rounds} />
            <DerivedRoadsPanel rounds={rounds} />
            <RecentWindow rounds={rounds} />
          </div>

          <div className="rounded-lg border border-border-dim bg-bg-card p-4">
            <RoundInputPanel
              onInput={handleInput}
              onRandomize={handleRandomize}
              onNewShoe={startNewShoe}
              disabled={loading || !currentShoe}
            />
          </div>

          <CardFaceDisplay round={rounds.length > 0 ? rounds[rounds.length - 1] : null} />
        </div>

        <div className="space-y-4">
          <div>
            <div className="text-sm font-semibold mb-2">📢 大路 Match 推薦排行榜</div>
            <MatchRanking match={latestMatch} />
          </div>
          <div>
            <div className="text-sm font-semibold mb-2">🎯 下三路推薦排行榜</div>
            <DerivedMatchRanking match={latestDerivedMatch} />
          </div>
          <div>
            <div className="text-sm font-semibold mb-2">🍀 Side Bet(Lucky 6)探索性統計</div>
            <SideBetPanel match={latestSideBetMatch} />
          </div>
          <HistoryLog history={matchHistory} rounds={rounds} />
          <div className="rounded-lg border border-border-dim bg-bg-card p-3">
            <ConnectionStatus />
          </div>
        </div>
      </div>

      <DebugInspector shoe={currentShoe} rounds={rounds} />
    </div>
  );
}
