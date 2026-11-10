import { create } from "zustand";
import type { DerivedMatchResult, MatchResult, RoundDoc, Shoe, SideBetMatchResult } from "../api/types";

export type WsStatus = "connecting" | "connected" | "disconnected";

interface AppState {
  // Shoe
  currentShoe: Shoe | null;
  rounds: RoundDoc[];
  setShoe: (shoe: Shoe) => void;
  setRounds: (rounds: RoundDoc[]) => void;
  addRoundLocal: (round: RoundDoc) => void;
  resetShoe: () => void;

  // Live matches (Big Road)
  latestMatch: MatchResult | null;
  matchHistory: MatchResult[];
  pushMatch: (match: MatchResult) => void;

  // Live matches (下三路 derived roads)
  latestDerivedMatch: DerivedMatchResult | null;
  derivedMatchHistory: DerivedMatchResult[];
  pushDerivedMatch: (match: DerivedMatchResult) => void;

  // Live matches (Side Bet / Lucky 6)
  latestSideBetMatch: SideBetMatchResult | null;
  sideBetMatchHistory: SideBetMatchResult[];
  pushSideBetMatch: (match: SideBetMatchResult) => void;

  // WebSocket
  wsStatus: WsStatus;
  wsLatencyMs: number | null;
  setWsStatus: (status: WsStatus) => void;
  setWsLatency: (ms: number) => void;

  // UI
  soundEnabled: boolean;
  toggleSound: () => void;
  debugExpanded: boolean;
  setDebugExpanded: (expanded: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentShoe: null,
  rounds: [],
  setShoe: (shoe) => set({ currentShoe: shoe }),
  setRounds: (rounds) => set({ rounds }),
  addRoundLocal: (round) =>
    set((s) => ({ rounds: [...s.rounds, round] })),
  resetShoe: () =>
    set({
      currentShoe: null,
      rounds: [],
      latestMatch: null,
      matchHistory: [],
      latestDerivedMatch: null,
      derivedMatchHistory: [],
      latestSideBetMatch: null,
      sideBetMatchHistory: [],
    }),

  latestMatch: null,
  matchHistory: [],
  pushMatch: (match) =>
    set((s) => {
      // De-dupe: the same match can arrive twice (once via the REST response,
      // once via the WebSocket broadcast). Both carry identical
      // shoeId+roundNo, so skip if we've already recorded this exact event.
      const isDuplicate =
        s.matchHistory[0]?.shoeId === match.shoeId &&
        s.matchHistory[0]?.roundNo === match.roundNo;
      if (isDuplicate) {
        return { latestMatch: match };
      }
      return {
        latestMatch: match,
        matchHistory: [match, ...s.matchHistory].slice(0, 50),
      };
    }),

  latestDerivedMatch: null,
  derivedMatchHistory: [],
  pushDerivedMatch: (match) =>
    set((s) => {
      const isDuplicate =
        s.derivedMatchHistory[0]?.shoeId === match.shoeId &&
        s.derivedMatchHistory[0]?.roundNo === match.roundNo;
      if (isDuplicate) {
        return { latestDerivedMatch: match };
      }
      return {
        latestDerivedMatch: match,
        derivedMatchHistory: [match, ...s.derivedMatchHistory].slice(0, 50),
      };
    }),

  latestSideBetMatch: null,
  sideBetMatchHistory: [],
  pushSideBetMatch: (match) =>
    set((s) => {
      const isDuplicate =
        s.sideBetMatchHistory[0]?.shoeId === match.shoeId &&
        s.sideBetMatchHistory[0]?.sourceRoundNo === match.sourceRoundNo;
      if (isDuplicate) {
        return { latestSideBetMatch: match };
      }
      return {
        latestSideBetMatch: match,
        sideBetMatchHistory: [match, ...s.sideBetMatchHistory].slice(0, 50),
      };
    }),

  wsStatus: "connecting",
  wsLatencyMs: null,
  setWsStatus: (status) => set({ wsStatus: status }),
  setWsLatency: (ms) => set({ wsLatencyMs: ms }),

  soundEnabled: false,
  toggleSound: () => set((s) => ({ soundEnabled: !s.soundEnabled })),
  debugExpanded: false,
  setDebugExpanded: (expanded) => set({ debugExpanded: expanded }),
}));
