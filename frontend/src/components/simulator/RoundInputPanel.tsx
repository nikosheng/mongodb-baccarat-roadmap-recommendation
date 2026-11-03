import { useEffect } from "react";
import type { Outcome } from "../../api/types";

interface Props {
  onInput: (result: Outcome) => void;
  onRandomize: (n: number) => void;
  onNewShoe: () => void;
  disabled?: boolean;
}

const BUTTONS: { outcome: Outcome; label: string; color: string; key: string }[] = [
  { outcome: "B", label: "莊 Banker", color: "bg-banker hover:brightness-110", key: "b" },
  { outcome: "P", label: "閒 Player", color: "bg-player hover:brightness-110", key: "p" },
  { outcome: "T", label: "和 Tie", color: "bg-tie hover:brightness-110", key: "t" },
];

export function RoundInputPanel({ onInput, onRandomize, onNewShoe, disabled }: Props) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      const match = BUTTONS.find((b) => b.key === key);
      if (match && !disabled) onInput(match.outcome);
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onInput, disabled]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        {BUTTONS.map((b) => (
          <button
            key={b.outcome}
            disabled={disabled}
            onClick={() => onInput(b.outcome)}
            className={`py-4 rounded-lg text-white font-bold text-lg transition disabled:opacity-40 ${b.color}`}
          >
            {b.label}
            <div className="text-xs font-normal opacity-80">鍵盤: {b.key.toUpperCase()}</div>
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          disabled={disabled}
          onClick={() => onRandomize(1)}
          className="flex-1 py-2 rounded-md bg-bg-card border border-border-dim text-sm hover:bg-border-dim disabled:opacity-40"
        >
          隨機 1 局
        </button>
        <button
          disabled={disabled}
          onClick={() => onRandomize(10)}
          className="flex-1 py-2 rounded-md bg-bg-card border border-border-dim text-sm hover:bg-border-dim disabled:opacity-40"
        >
          隨機 10 局
        </button>
        <button
          onClick={onNewShoe}
          className="flex-1 py-2 rounded-md bg-bg-card border border-accent-gold text-accent-gold text-sm hover:bg-accent-gold hover:text-bg-deep"
        >
          新靴
        </button>
      </div>
    </div>
  );
}
