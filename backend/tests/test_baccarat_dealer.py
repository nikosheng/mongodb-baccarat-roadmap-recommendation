"""Unit tests for the baccarat dealing engine (card values/mod-10, natural,
player/banker draw rules, no-repeat deck, cut-card behavior, Lucky 6
labeling)."""

from __future__ import annotations

import random

import pytest

from app.services import baccarat_dealer as bd


def _queue_draw_fn(cards: list[bd.Card]):
    it = iter(cards)

    def draw():
        return next(it)

    return draw


def test_card_values_and_mod10():
    assert bd.Card("A", "S").value == 1
    for r in ["2", "3", "4", "5", "6", "7", "8", "9"]:
        assert bd.Card(r, "S").value == int(r)
    for r in ["10", "J", "Q", "K"]:
        assert bd.Card(r, "S").value == 0


def test_build_shoe_cards_no_duplicates_within_a_deck_count():
    rng = random.Random(42)
    cards = bd.build_shoe_cards(rng, num_decks=8)
    assert len(cards) == 416
    # Exactly 8 copies of every (rank, suit) pair, no more no less.
    from collections import Counter

    counts = Counter((c.rank, c.suit) for c in cards)
    assert len(counts) == 13 * 4
    assert all(v == 8 for v in counts.values())


def test_natural_banker_no_draw():
    cards = [
        bd.Card("5", "S"),  # player 1
        bd.Card("9", "H"),  # banker 1
        bd.Card("3", "S"),  # player 2 -> total 8
        bd.Card("K", "H"),  # banker 2 -> total 9
    ]
    hand = bd.deal_hand(_queue_draw_fn(cards))
    assert hand.playerTotal == 8
    assert hand.bankerTotal == 9
    assert hand.naturalType == "both_natural"
    assert hand.playerCardCount == 2
    assert hand.bankerCardCount == 2
    assert hand.result == "B"
    assert hand.margin == 1


def test_player_draws_on_0_to_5_and_stands_on_6_7():
    # Player total 6 (no draw), banker total 5 draws because no_third col is True.
    cards = [
        bd.Card("4", "S"),  # player1
        bd.Card("2", "H"),  # banker1
        bd.Card("2", "S"),  # player2 -> total 6, stands
        bd.Card("3", "H"),  # banker2 -> total 5, no_third col True -> draw
        bd.Card("K", "D"),  # banker3 -> value 0, total stays 5
    ]
    hand = bd.deal_hand(_queue_draw_fn(cards))
    assert hand.playerTotal == 6
    assert hand.playerCardCount == 2
    assert hand.bankerCardCount == 3
    assert hand.bankerTotal == 5
    assert hand.result == "P"


@pytest.mark.parametrize(
    "banker_total,player_third,expected_draw",
    [
        (0, None, True),
        (2, 9, True),
        (7, 9, False),
        (7, None, False),
        (3, 8, False),
        (3, 9, True),
        (4, 0, False),
        (4, 1, False),
        (4, 2, True),
        (4, 8, False),
        (5, 3, False),
        (5, 4, True),
        (5, None, True),
        (6, None, False),
        (6, 6, True),
        (6, 7, True),
        (6, 5, False),
    ],
)
def test_banker_draw_table(banker_total, player_third, expected_draw):
    assert bd._banker_draws(banker_total, player_third) == expected_draw


def test_banker_table_total_and_natural_full_hand_from_plan_demo_round1():
    # Demo round 1 from docs/side-bet-lucky6-plan.md §12.1:
    # Banker 5H,4C -> 9 ; Player 6S,10D -> 6 ; natural banker.
    cards = [
        bd.Card("6", "S"),  # player1
        bd.Card("5", "H"),  # banker1
        bd.Card("10", "D"),  # player2 -> total 6
        bd.Card("4", "C"),  # banker2 -> total 9
    ]
    hand = bd.deal_hand(_queue_draw_fn(cards))
    assert hand.playerTotal == 6
    assert hand.bankerTotal == 9
    assert hand.result == "B"
    assert hand.margin == 3
    assert hand.naturalType == "banker_natural"


def test_pair_and_perfect_pair_detection():
    cards = [
        bd.Card("6", "S"),  # player1
        bd.Card("K", "H"),  # banker1
        bd.Card("6", "S"),  # player2 -> same rank+suit as player1 -> perfect pair; total 2, draws
        bd.Card("K", "D"),  # banker2 -> same rank, diff suit -> pair only; total 0
        bd.Card("9", "C"),  # player third -> total 11 % 10 = 1
        bd.Card("3", "H"),  # banker third (0 draws regardless) -> total 3
    ]
    hand = bd.deal_hand(_queue_draw_fn(cards))
    assert hand.playerPair is True
    assert hand.playerPerfectPair is True
    assert hand.bankerPair is True
    assert hand.bankerPerfectPair is False


@pytest.mark.parametrize(
    "result,banker_total,banker_card_count,expected",
    [
        ("B", 6, 2, "banker_6_two_cards"),
        ("B", 6, 3, "banker_6_three_cards"),
        ("B", 7, 2, "none"),
        ("P", 6, 2, "none"),
        ("T", 6, 3, "none"),
    ],
)
def test_lucky6_classification(result, banker_total, banker_card_count, expected):
    assert bd._lucky6(result, banker_total, banker_card_count) == expected


def test_dealer_shoe_cut_card_and_registry_lifecycle():
    dealer = bd.DealerShoe.new(seed=7, cut_card_buffer=410)
    assert dealer.cards_remaining() == 416
    assert dealer.can_deal_hand() is True

    hand = dealer.deal_hand()
    assert isinstance(hand, bd.HandResult)
    assert dealer.hands_dealt == 1
    # A hand consumes 4-6 cards; remaining must have shrunk correspondingly.
    assert dealer.cards_remaining() == 416 - hand.totalCardCount

    # Force the shoe past its cut-card by draining it further.
    while dealer.can_deal_hand():
        dealer.deal_hand()
    with pytest.raises(bd.ShoeExhaustedError):
        dealer.deal_hand()


def test_dealer_shoe_never_deals_the_same_physical_card_twice():
    dealer = bd.DealerShoe.new(seed=123, cut_card_buffer=20)
    seen_positions: set[int] = set()
    while dealer.can_deal_hand():
        start = dealer.position
        hand = dealer.deal_hand()
        end = dealer.position
        new_positions = set(range(start, end))
        assert not (new_positions & seen_positions)
        seen_positions |= new_positions
        assert end - start == hand.totalCardCount


def test_shoe_registry_start_get_discard():
    bd.start_dealer_shoe("shoe_test_1", seed=1)
    assert bd.get_dealer_shoe("shoe_test_1") is not None
    bd.discard_dealer_shoe("shoe_test_1")
    assert bd.get_dealer_shoe("shoe_test_1") is None
