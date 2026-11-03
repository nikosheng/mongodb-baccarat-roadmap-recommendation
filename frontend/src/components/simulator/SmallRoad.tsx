import type { DerivedCell } from "../../lib/roads";
import { DerivedRoadCanvas } from "./DerivedRoadCanvas";

export function SmallRoad({ cells }: { cells: DerivedCell[] }) {
  return (
    <div className="flex items-center gap-2">
      <div className="text-xs text-text-muted w-16 shrink-0">小路</div>
      <div className="overflow-x-auto border border-border-dim rounded bg-bg-deep p-1">
        <DerivedRoadCanvas cells={cells} variant="solid-dot" />
      </div>
    </div>
  );
}
