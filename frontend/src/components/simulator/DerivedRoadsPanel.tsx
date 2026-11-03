import { useMemo } from "react";
import type { RoundDoc } from "../../api/types";
import { computeAllRoads } from "../../lib/roads";
import { BigEyeRoad } from "./BigEyeRoad";
import { SmallRoad } from "./SmallRoad";
import { CockroachRoad } from "./CockroachRoad";

export function DerivedRoadsPanel({ rounds }: { rounds: RoundDoc[] }) {
  const roads = useMemo(() => computeAllRoads(rounds), [rounds]);

  const hasAnyDerivedData =
    roads.bigEye.length > 0 || roads.small.length > 0 || roads.cockroach.length > 0;

  return (
    <details className="rounded-lg border border-border-dim bg-bg-card p-3" open>
      <summary className="text-sm font-semibold cursor-pointer select-none">
        下三路 (Big Eye Boy / Small Road / Cockroach Pig)
      </summary>
      <div className="mt-3 space-y-2">
        {!hasAnyDerivedData && (
          <div className="text-xs text-text-muted">
            局數還不夠,下三路要等大路累積到第 3~4 列才會開始顯示
          </div>
        )}
        <BigEyeRoad cells={roads.bigEye} />
        <SmallRoad cells={roads.small} />
        <CockroachRoad cells={roads.cockroach} />
      </div>
    </details>
  );
}
