import { useEffect, useRef } from "react";
import type { DerivedCell } from "../../lib/roads";
import { ROAD_ROWS } from "../../lib/roads";

const CELL = 16;
const COLORS: Record<"R" | "B", string> = { R: "#dc2626", B: "#2563eb" };

export type DerivedRoadVariant = "hollow-circle" | "solid-dot" | "diagonal-line";

/** Shared canvas renderer for the three 下三路 (Big Eye Boy / Small Road /
 * Cockroach Pig), each distinguished only by its marker shape per
 * convention: hollow red/blue circles, solid red/blue dots, and red/blue
 * diagonal slashes respectively. */
export function DerivedRoadCanvas({
  cells,
  variant,
}: {
  cells: DerivedCell[];
  variant: DerivedRoadVariant;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const maxCol = cells.length ? Math.max(...cells.map((c) => c.col)) : 0;
    const width = Math.max(120, (maxCol + 2) * CELL);
    const height = ROAD_ROWS * CELL + 6;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 0.5;
    for (let c = 0; c <= maxCol + 1; c++) {
      ctx.beginPath();
      ctx.moveTo(c * CELL, 0);
      ctx.lineTo(c * CELL, ROAD_ROWS * CELL);
      ctx.stroke();
    }
    for (let r = 0; r <= ROAD_ROWS; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * CELL);
      ctx.lineTo((maxCol + 2) * CELL, r * CELL);
      ctx.stroke();
    }

    for (const cell of cells) {
      const cx = cell.col * CELL + CELL / 2;
      const cy = cell.row * CELL + CELL / 2;
      const radius = CELL / 2 - 3;
      const color = COLORS[cell.color];

      if (variant === "hollow-circle") {
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else if (variant === "solid-dot") {
        ctx.beginPath();
        ctx.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.moveTo(cx - radius * 0.7, cy + radius * 0.7);
        ctx.lineTo(cx + radius * 0.7, cy - radius * 0.7);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }
  }, [cells, variant]);

  return <canvas ref={canvasRef} />;
}
