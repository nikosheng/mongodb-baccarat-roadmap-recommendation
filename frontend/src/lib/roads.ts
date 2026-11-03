/**
 * Shared road-layout algorithms used by the Big Road and the three derived
 * roads (Big Eye Boy, Small Road, Cockroach Pig).
 *
 * CRITICAL INVARIANT: this file must stay behaviorally identical to the
 * Python implementation in `backend/app/services/derived_roads.py`. Both
 * sides are exercised against the same fixture file
 * (`backend/tests/fixtures/road_cases.json`) to guarantee parity — the
 * frontend renders roads instantly from local state while the backend
 * computes the same roads to build NL text for vector search, and if the
 * two disagree the displayed grids and the recommendation panel will look
 * inconsistent to the user.
 *
 * Big Road layout rules (standard casino "Big Road"):
 *   - Same outcome as previous -> extends downward in the same column.
 *   - Different outcome -> opens a new column, starting at row 0.
 *   - When a streak reaches the bottom row (row = ROWS-1) and continues,
 *     it "tails": each subsequent same-outcome result moves one column to
 *     the right while staying pinned to the bottom row, until the streak
 *     breaks.
 *   - Tie does not open a new column or break a streak; it's recorded as
 *     a counter on the most recently placed cell. Ties before the first
 *     B/P attach to that first result; a tie-only shoe uses a placeholder.
 *
 * Derived road rule (Big Eye Boy / Small Road / Cockroach Pig), generalized
 * by `offset` (1 / 2 / 3 respectively):
 *   For each newly placed Big Road B/P cell at (col, row):
 *     - If row > 0 (continuing a column): compare whether column
 *       (col - offset) has a cell at this same row index. If yes -> Red,
 *       else -> Blue.
 *     - If row == 0 (a brand new column): compare the total height of
 *       column (col - offset) vs column (col - offset - 1). Equal -> Red,
 *       different -> Blue.
 *   Not enough history yet (referenced column index < 0) -> no symbol yet.
 *   The resulting R/B symbol sequence is then laid out on its own road
 *   using the same down-then-tail algorithm as the Big Road.
 */

export type Outcome = "B" | "P" | "T";
export type RoadColor = "R" | "B";

export const ROAD_ROWS = 6;

export interface BigRoadCell {
  col: number;
  row: number;
  symbol: Outcome; // "T" only when a shoe has ties and no B/P result
  tieCount: number;
}

export interface DerivedCell {
  col: number;
  row: number;
  color: RoadColor;
}

interface MinimalRound {
  result: Outcome;
}

/** Generic down-then-tail layout for a sequence of same/different symbols. */
function layoutRunSequence<T extends string>(
  symbols: T[]
): Array<{ col: number; row: number; symbol: T }> {
  const out: Array<{ col: number; row: number; symbol: T }> = [];
  let col = 0;
  let row = 0;
  let last: T | null = null;
  let tailing = false;

  for (const s of symbols) {
    if (last === null) {
      col = 0;
      row = 0;
    } else if (s === last) {
      if (tailing) {
        col += 1;
      } else if (row + 1 < ROAD_ROWS) {
        row += 1;
      } else {
        tailing = true;
        col += 1;
        row = ROAD_ROWS - 1;
      }
    } else {
      col += 1;
      row = 0;
      tailing = false;
    }
    last = s;
    out.push({ col, row, symbol: s });
  }

  return out;
}

/**
 * Compute the Big Road cell layout from a round sequence.
 * Only "B"/"P" results participate in the column/row algorithm; "T"
 * results are folded into `tieCount` on the previous cell. Leading ties
 * attach to the first B/P cell; a placeholder is emitted only if no B/P
 * result appears in the sequence.
 */
export function layoutBigRoad(rounds: MinimalRound[]): BigRoadCell[] {
  const cells: BigRoadCell[] = [];
  const bpSymbols: Outcome[] = [];

  // First pass: build the B/P-only run and remember where leading/attached
  // ties go.
  let pendingLeadingTies = 0;
  const tieCountsAfterIndex: number[] = []; // ties immediately following bpSymbols[i]
  for (const r of rounds) {
    if (r.result === "T") {
      if (bpSymbols.length === 0) {
        pendingLeadingTies += 1;
      } else {
        tieCountsAfterIndex[bpSymbols.length - 1] =
          (tieCountsAfterIndex[bpSymbols.length - 1] ?? 0) + 1;
      }
      continue;
    }
    bpSymbols.push(r.result);
  }

  if (pendingLeadingTies > 0) {
    if (bpSymbols.length > 0) {
      // With no previous B/P cell, carry leading ties onto the first
      // resolved outcome so the tie slash shares that cell.
      tieCountsAfterIndex[0] =
        (tieCountsAfterIndex[0] ?? 0) + pendingLeadingTies;
    } else {
      // A shoe containing only ties still needs a visible placeholder.
      cells.push({ col: 0, row: 0, symbol: "T", tieCount: pendingLeadingTies });
    }
  }

  const laidOut = layoutRunSequence(bpSymbols);
  laidOut.forEach((c, i) => {
    cells.push({
      col: c.col,
      row: c.row,
      symbol: c.symbol,
      tieCount: tieCountsAfterIndex[i] ?? 0,
    });
  });

  return cells;
}

/** Column -> total number of cells placed in that column (its "height"). */
function columnHeights(bpCells: BigRoadCell[]): Map<number, number> {
  const heights = new Map<number, number>();
  for (const c of bpCells) {
    heights.set(c.col, (heights.get(c.col) ?? 0) + 1);
  }
  return heights;
}

/**
 * Compute one derived road (Big Eye Boy / Small Road / Cockroach Pig) from
 * the Big Road's B/P cells. `offset` is 1 for Big Eye Boy, 2 for Small
 * Road, 3 for Cockroach Pig.
 */
export function computeDerivedRoad(bigRoadCells: BigRoadCell[], offset: number): DerivedCell[] {
  const bpCells = bigRoadCells.filter((c) => c.symbol === "B" || c.symbol === "P");
  const heights = new Map<number, number>();
  const occupiedRows = new Map<number, Set<number>>();
  const symbols: RoadColor[] = [];

  for (const cell of bpCells) {
    heights.set(cell.col, (heights.get(cell.col) ?? 0) + 1);
    const rows = occupiedRows.get(cell.col) ?? new Set<number>();
    rows.add(cell.row);
    occupiedRows.set(cell.col, rows);
    const { col, row } = cell;
    const left1 = col - offset;
    const left2 = col - offset - 1;

    if (left1 < 0) continue;

    if (row > 0) {
      const exists = occupiedRows.get(left1)?.has(row) ?? false;
      symbols.push(exists ? "R" : "B");
    } else {
      if (left2 < 0) continue;
      const h1 = heights.get(left1) ?? 0;
      const h2 = heights.get(left2) ?? 0;
      symbols.push(h1 === h2 ? "R" : "B");
    }
  }

  const laidOut = layoutRunSequence(symbols);
  return laidOut.map((c) => ({ col: c.col, row: c.row, color: c.symbol }));
}

export function computeAllRoads(rounds: MinimalRound[]) {
  const bigRoad = layoutBigRoad(rounds);
  return {
    bigRoad,
    bigEye: computeDerivedRoad(bigRoad, 1),
    small: computeDerivedRoad(bigRoad, 2),
    cockroach: computeDerivedRoad(bigRoad, 3),
  };
}

/** Extract the tail (most recent K) R/B symbols from a derived road, in
 * chronological order — used to build the NL description for vector search. */
export function tailSymbols(cells: DerivedCell[], k = 12): string {
  return cells
    .slice(-k)
    .map((c) => c.color)
    .join("");
}

// Re-export columnHeights for potential debug use.
export { columnHeights };
