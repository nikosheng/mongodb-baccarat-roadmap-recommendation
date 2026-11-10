"""Real baccarat dealing engine: builds an 8-deck shoe, shuffles it, and
deals hands using the standard baccarat drawing rules (natural, player
third-card rule, banker third-card table). B/P/T and all Lucky 6-relevant
fields (banker/player totals, card counts, pairs, natural type) are derived
from the actual dealt cards — never from an independent probability table.

Deck/cut-card state must persist across API requests for the lifetime of a
shoe (see docs/side-bet-lucky6-plan.md §3.1): this module keeps one
`DealerShoe` per `shoeId` in an in-process registry. This is adequate for
this single-process demo deployment (same assumption the rest of the app
already makes - e.g. `broadcaster.manager`'s in-memory WebSocket
connections); it does not survive a backend restart, which is acceptable
for a demo/dev server and mirrors how the existing app already behaves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]

RANK_VALUES: dict[str, int] = {
    "A": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 0,
    "J": 0,
    "Q": 0,
    "K": 0,
}

NUM_DECKS = 8
CARDS_PER_SHOE = NUM_DECKS * len(RANKS) * len(SUITS)  # 416

# Demo cut-card rule: the shoe cannot start a new hand once fewer than this
# many cards remain (a real cut-card is placed ~14-18 cards from the back of
# an 8-deck shoe; a hand needs up to 6 cards, so we require a modest buffer
# on top of that so a hand is never started that it can't finish).
DEFAULT_CUT_CARD_BUFFER = 20

Outcome = Literal["B", "P", "T"]
NaturalType = Literal["none", "banker_natural", "player_natural", "both_natural"]
Lucky6Result = Literal["none", "banker_6_two_cards", "banker_6_three_cards"]


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return RANK_VALUES[self.rank]

    def to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}


def _total(cards: list[Card]) -> int:
    return sum(c.value for c in cards) % 10


def _is_pair(cards: list[Card]) -> bool:
    return len(cards) >= 2 and cards[0].rank == cards[1].rank


def _is_perfect_pair(cards: list[Card]) -> bool:
    return len(cards) >= 2 and cards[0].rank == cards[1].rank and cards[0].suit == cards[1].suit


# Banker's third-card draw table. Keys are banker's two-card total (3/4/5/6);
# 0-2 always draw and 7 always stands regardless of the player's third card,
# so they're handled directly in `_banker_draws` rather than listed here.
# `no_third` is the column used when the player did NOT draw a third card.
_BANKER_DRAW_TABLE: dict[int, dict] = {
    3: {"no_third": True, 0: True, 1: True, 2: True, 3: True, 4: True, 5: True, 6: True, 7: True, 8: False, 9: True},
    4: {"no_third": True, 0: False, 1: False, 2: True, 3: True, 4: True, 5: True, 6: True, 7: True, 8: False, 9: False},
    5: {"no_third": True, 0: False, 1: False, 2: False, 3: False, 4: True, 5: True, 6: True, 7: True, 8: False, 9: False},
    6: {"no_third": False, 0: False, 1: False, 2: False, 3: False, 4: False, 5: False, 6: True, 7: True, 8: False, 9: False},
}


def _banker_draws(banker_total: int, player_third_value: int | None) -> bool:
    if banker_total <= 2:
        return True
    if banker_total == 7:
        return False
    row = _BANKER_DRAW_TABLE[banker_total]
    if player_third_value is None:
        return row["no_third"]
    return row[player_third_value]


@dataclass
class HandResult:
    bankerCards: list[Card]
    playerCards: list[Card]
    bankerTotal: int
    playerTotal: int
    result: Outcome
    margin: int
    bankerCardCount: int
    playerCardCount: int
    totalCardCount: int
    bankerPair: bool
    playerPair: bool
    bankerPerfectPair: bool
    playerPerfectPair: bool
    naturalType: NaturalType
    lucky6Result: Lucky6Result


def _lucky6(result: Outcome, banker_total: int, banker_card_count: int) -> Lucky6Result:
    if result != "B" or banker_total != 6:
        return "none"
    if banker_card_count == 2:
        return "banker_6_two_cards"
    return "banker_6_three_cards"


def deal_hand(draw_fn) -> HandResult:
    """Deal one hand using `draw_fn()` to pull the next card from whatever
    shoe/deck is backing it. Pure function of the draw sequence — used both
    by `DealerShoe.deal_hand()` (live app) and directly by the Monte Carlo
    seed script against its own deck objects, so both paths run identical
    baccarat rules."""
    # Casino dealing order: player, banker, player, banker.
    player_cards = [draw_fn()]
    banker_cards = [draw_fn()]
    player_cards.append(draw_fn())
    banker_cards.append(draw_fn())

    player_total = _total(player_cards)
    banker_total = _total(banker_cards)

    banker_pair = _is_pair(banker_cards)
    player_pair = _is_pair(player_cards)
    banker_perfect_pair = _is_perfect_pair(banker_cards)
    player_perfect_pair = _is_perfect_pair(player_cards)

    is_natural = player_total >= 8 or banker_total >= 8
    if is_natural:
        if banker_total >= 8 and player_total >= 8:
            natural_type: NaturalType = "both_natural"
        elif banker_total >= 8:
            natural_type = "banker_natural"
        else:
            natural_type = "player_natural"
    else:
        natural_type = "none"

    if not is_natural:
        player_third_value: int | None = None
        if player_total <= 5:
            card = draw_fn()
            player_cards.append(card)
            player_third_value = card.value
            player_total = _total(player_cards)

        if _banker_draws(banker_total, player_third_value):
            card = draw_fn()
            banker_cards.append(card)
            banker_total = _total(banker_cards)

    if banker_total > player_total:
        result: Outcome = "B"
    elif player_total > banker_total:
        result = "P"
    else:
        result = "T"

    margin = banker_total - player_total
    banker_card_count = len(banker_cards)
    player_card_count = len(player_cards)

    return HandResult(
        bankerCards=banker_cards,
        playerCards=player_cards,
        bankerTotal=banker_total,
        playerTotal=player_total,
        result=result,
        margin=margin,
        bankerCardCount=banker_card_count,
        playerCardCount=player_card_count,
        totalCardCount=banker_card_count + player_card_count,
        bankerPair=banker_pair,
        playerPair=player_pair,
        bankerPerfectPair=banker_perfect_pair,
        playerPerfectPair=player_perfect_pair,
        naturalType=natural_type,
        lucky6Result=_lucky6(result, banker_total, banker_card_count),
    )


def build_shoe_cards(rng: random.Random, num_decks: int = NUM_DECKS) -> list[Card]:
    cards = [Card(rank=r, suit=s) for _ in range(num_decks) for s in SUITS for r in RANKS]
    rng.shuffle(cards)
    return cards


class ShoeExhaustedError(RuntimeError):
    """Raised when a hand is requested but the shoe has passed the
    cut-card point and cannot deal another full hand."""


@dataclass
class DealerShoe:
    """Persistent per-shoe deck + cut-card state. One instance backs one
    `shoeId` for its entire lifetime; it is never reshuffled mid-shoe."""

    cards: list[Card]
    cut_card_buffer: int = DEFAULT_CUT_CARD_BUFFER
    position: int = 0
    hands_dealt: int = 0

    @classmethod
    def new(cls, seed: int | None = None, cut_card_buffer: int = DEFAULT_CUT_CARD_BUFFER) -> "DealerShoe":
        rng = random.Random(seed)
        return cls(cards=build_shoe_cards(rng), cut_card_buffer=cut_card_buffer)

    def cards_remaining(self) -> int:
        return len(self.cards) - self.position

    def can_deal_hand(self) -> bool:
        """Conservative check used before starting a new hand: once fewer
        than `cut_card_buffer` cards remain, the shoe is past its cut-card
        and must be closed (a new shoe started) rather than reshuffled."""
        return self.cards_remaining() > self.cut_card_buffer

    def _draw(self) -> Card:
        if self.position >= len(self.cards):
            raise ShoeExhaustedError("deck has no cards left")
        card = self.cards[self.position]
        self.position += 1
        return card

    def deal_hand(self) -> HandResult:
        if not self.can_deal_hand():
            raise ShoeExhaustedError(
                f"shoe is past its cut-card ({self.cards_remaining()} cards left); start a new shoe"
            )
        hand = deal_hand(self._draw)
        self.hands_dealt += 1
        return hand


_shoe_registry: dict[str, DealerShoe] = {}


def start_dealer_shoe(shoe_id: str, seed: int | None = None) -> DealerShoe:
    """Create (and register) a fresh dealer shoe for `shoe_id`, replacing
    any previous one. Call this whenever a new logical baccarat shoe is
    started (e.g. `create_shoe`)."""
    dealer = DealerShoe.new(seed=seed)
    _shoe_registry[shoe_id] = dealer
    return dealer


def get_dealer_shoe(shoe_id: str) -> DealerShoe | None:
    return _shoe_registry.get(shoe_id)


def discard_dealer_shoe(shoe_id: str) -> None:
    _shoe_registry.pop(shoe_id, None)
