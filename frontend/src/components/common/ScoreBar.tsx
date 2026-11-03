export function ScoreBar({ score, highlight = false }: { score: number; highlight?: boolean }) {
  const pct = Math.max(0, Math.min(1, score)) * 100;
  return (
    <div className="w-full h-2 bg-border-dim rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${
          highlight ? "bg-accent-gold" : "bg-player"
        }`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
