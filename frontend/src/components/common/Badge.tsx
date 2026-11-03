import type { Outcome } from "../../api/types";

const OUTCOME_CONFIG: Record<Outcome, { label: string; color: string }> = {
  B: { label: "莊 B", color: "bg-banker" },
  P: { label: "閒 P", color: "bg-player" },
  T: { label: "和 T", color: "bg-tie" },
};

export function OutcomeBadge({ outcome, size = "md" }: { outcome: Outcome; size?: "sm" | "md" | "lg" }) {
  const cfg = OUTCOME_CONFIG[outcome];
  const sizeClass =
    size === "sm" ? "px-2 py-0.5 text-xs" : size === "lg" ? "px-4 py-2 text-lg" : "px-3 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center justify-center rounded-md font-bold text-white ${cfg.color} ${sizeClass}`}
    >
      {cfg.label}
    </span>
  );
}
