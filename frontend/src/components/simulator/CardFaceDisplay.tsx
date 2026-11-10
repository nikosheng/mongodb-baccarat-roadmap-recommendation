import type { CardDto, RoundDoc } from "../../api/types";
import { OutcomeBadge } from "../common/Badge";

const SUIT_SYMBOL: Record<string, string> = { S: "♠", H: "♥", D: "♦", C: "♣" };
const RED_SUITS = new Set(["H", "D"]);

function CardChip({ card }: { card: CardDto }) {
  const isRed = RED_SUITS.has(card.suit);
  return (
    <span
      className={`inline-flex items-center justify-center min-w-[2.25rem] px-1.5 py-1 rounded border border-border-dim bg-bg-deep font-mono-seq text-sm font-semibold ${
        isRed ? "text-tie" : "text-text-primary"
      }`}
    >
      {card.rank}
      {SUIT_SYMBOL[card.suit] ?? card.suit}
    </span>
  );
}

const LUCKY6_LABEL: Record<string, string> = {
  banker_6_two_cards: "Lucky 6(兩張)",
  banker_6_three_cards: "Lucky 6(三張)",
};

/** Shows the latest auto-dealt round's actual card faces. Manual B/P/T
 * entries have no card data (see docs/side-bet-lucky6-plan.md §3.2) and are
 * shown with an explicit "沒有牌面資料" message instead of guessing/omitting
 * silently. */
export function CardFaceDisplay({ round }: { round: RoundDoc | null }) {
  if (!round) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-3 text-text-muted text-sm">
        尚無局數
      </div>
    );
  }

  if (round.source !== "random_sim" || !round.bankerCards || !round.playerCards) {
    return (
      <div className="rounded-lg border border-border-dim bg-bg-card p-3 text-text-muted text-sm">
        Round {round.roundNo}:手動輸入 B/P/T,沒有牌面資料
      </div>
    );
  }

  const lucky6Label =
    round.lucky6Result && round.lucky6Result !== "none" ? LUCKY6_LABEL[round.lucky6Result] : null;

  return (
    <div className="rounded-lg border border-border-dim bg-bg-card p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-text-muted">Round {round.roundNo} 牌面</span>
        <div className="flex items-center gap-2">
          {lucky6Label && (
            <span className="text-xs px-2 py-0.5 rounded bg-accent-gold/20 text-accent-gold font-semibold">
              {lucky6Label}
            </span>
          )}
          <OutcomeBadge outcome={round.result} size="sm" />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-text-muted w-8">莊</span>
        <div className="flex gap-1">
          {round.bankerCards.map((c, i) => (
            <CardChip key={i} card={c} />
          ))}
        </div>
        <span className="text-sm font-mono-seq text-text-primary ml-auto">{round.bankerTotal}</span>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-text-muted w-8">閒</span>
        <div className="flex gap-1">
          {round.playerCards.map((c, i) => (
            <CardChip key={i} card={c} />
          ))}
        </div>
        <span className="text-sm font-mono-seq text-text-primary ml-auto">{round.playerTotal}</span>
      </div>

      <div className="text-xs text-text-muted">
        margin {round.margin != null && round.margin > 0 ? `+${round.margin}` : round.margin} · 共{" "}
        {round.totalCardCount} 張
        {round.bankerPair && " · 莊對子"}
        {round.playerPair && " · 閒對子"}
      </div>
    </div>
  );
}
