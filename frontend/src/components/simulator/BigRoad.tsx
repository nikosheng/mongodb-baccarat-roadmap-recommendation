import { useEffect, useRef } from "react";
import type { Outcome, RoundDoc } from "../../api/types";
import { layoutBigRoad, ROAD_ROWS } from "../../lib/roads";

const CELL = 26;
const ROWS = ROAD_ROWS;
const COLORS: Record<Outcome, string> = {
  B: "#dc2626",
  P: "#2563eb",
  T: "#16a34a",
};

export function BigRoad({ rounds }: { rounds: RoundDoc[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const cells = layoutBigRoad(rounds);
    const maxCol = cells.length ? Math.max(...cells.map((c) => c.col)) : 0;
    const width = Math.max(300, (maxCol + 2) * CELL);
    const height = ROWS * CELL + 10;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // grid lines
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 0.5;
    for (let c = 0; c <= maxCol + 1; c++) {
      ctx.beginPath();
      ctx.moveTo(c * CELL, 0);
      ctx.lineTo(c * CELL, ROWS * CELL);
      ctx.stroke();
    }
    for (let rI = 0; rI <= ROWS; rI++) {
      ctx.beginPath();
      ctx.moveTo(0, rI * CELL);
      ctx.lineTo((maxCol + 2) * CELL, rI * CELL);
      ctx.stroke();
    }

    for (const cell of cells) {
      const cx = cell.col * CELL + CELL / 2;
      const cy = cell.row * CELL + CELL / 2;
      const radius = CELL / 2 - 4;

      if (cell.symbol !== "T" || cell.tieCount === 0) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = COLORS[cell.symbol];
        ctx.fill();
      }

      if (cell.tieCount > 0) {
        ctx.strokeStyle = COLORS.T;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx - radius * 0.7, cy + radius * 0.7);
        ctx.lineTo(cx + radius * 0.7, cy - radius * 0.7);
        ctx.stroke();
        if (cell.tieCount > 1) {
          ctx.fillStyle = "#16a34a";
          ctx.font = "10px sans-serif";
          ctx.fillText(String(cell.tieCount), cx + radius * 0.3, cy - radius * 0.3);
        }
      }
    }
  }, [rounds]);

  return (
    <div className="overflow-x-auto border border-border-dim rounded-lg bg-bg-deep p-2">
      <canvas ref={canvasRef} />
    </div>
  );
}
