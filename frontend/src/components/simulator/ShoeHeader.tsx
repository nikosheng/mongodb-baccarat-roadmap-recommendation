import type { Shoe } from "../../api/types";

export function ShoeHeader({ shoe }: { shoe: Shoe | null }) {
  if (!shoe) {
    return <div className="text-text-muted">尚未開靴</div>;
  }
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-sm text-text-muted">Shoe</div>
        <div className="font-mono-seq">{shoe.shoeId}</div>
      </div>
      <div className="flex gap-4 text-sm">
        <div>
          局數 <span className="font-semibold">{shoe.totalRounds}</span>
        </div>
        <div className="text-banker">B {shoe.summary.B}</div>
        <div className="text-player">P {shoe.summary.P}</div>
        <div className="text-tie">T {shoe.summary.T}</div>
      </div>
    </div>
  );
}
