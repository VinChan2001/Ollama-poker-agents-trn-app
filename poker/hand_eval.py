from treys import Card, Evaluator

RANK_ORDER = "23456789TJQKA"

RANK_NAMES = {
    "2": "Twos",
    "3": "Threes",
    "4": "Fours",
    "5": "Fives",
    "6": "Sixes",
    "7": "Sevens",
    "8": "Eights",
    "9": "Nines",
    "T": "Tens",
    "J": "Jacks",
    "Q": "Queens",
    "K": "Kings",
    "A": "Aces",
}

SINGULAR_RANK_NAMES = {
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "6": "Six",
    "7": "Seven",
    "8": "Eight",
    "9": "Nine",
    "T": "Ten",
    "J": "Jack",
    "Q": "Queen",
    "K": "King",
    "A": "Ace",
}


def _rank_value(rank):
    return RANK_ORDER.index(rank) + 2


def _card_rank(card):
    return card[0]


def _card_suit(card):
    return card[1]

def _best_score(cards, board):
    evaluator = Evaluator()
    return evaluator.evaluate(
        [convert_card(c) for c in board],
        [convert_card(c) for c in cards],
    )

def convert_card(card: str):
    return Card.new(card)

def _score_hand(player_cards, community_cards):
    evaluator = Evaluator()
    board = [convert_card(c) for c in community_cards]
    hand = [convert_card(c) for c in player_cards]
    return evaluator.evaluate(board, hand)

def _analyze_private_card_usage(player_cards, community_cards):
    """
    Estimates whether the player's private cards actually improve the board.

    This is not a perfect 5-card extractor, but it is very useful for strategy:
    - board_only_made_hand=True means the player's best made hand is basically shared.
    - private_contribution tells the LLM whether the hand is real or just board texture.
    """
    if len(community_cards) < 3:
        return {
            "hole_cards_used_count": 2,
            "board_only_made_hand": False,
            "private_contribution": "preflop private cards define the hand",
        }

    evaluator = Evaluator()

    player_score = _score_hand(player_cards, community_cards)

    # If 5 community cards exist, compare player hand to board-only hand.
    # Treys needs exactly 2 hand cards, so simulate board-only by checking
    # whether replacing player's private cards with irrelevant dead cards gives same score is awkward.
    # Instead, use rank/suit contribution heuristics below.
    player_ranks = [_card_rank(c) for c in player_cards]
    board_ranks = [_card_rank(c) for c in community_cards]
    player_suits = [_card_suit(c) for c in player_cards]
    board_suits = [_card_suit(c) for c in community_cards]

    rank_counts_board = {r: board_ranks.count(r) for r in set(board_ranks)}
    rank_counts_all = {r: (player_ranks + board_ranks).count(r) for r in set(player_ranks + board_ranks)}

    contributing_cards = 0
    contribution_notes = []

    for card in player_cards:
        rank = _card_rank(card)
        suit = _card_suit(card)

        rank_improves_pairing = rank_counts_all.get(rank, 0) > rank_counts_board.get(rank, 0) and rank_counts_all.get(rank, 0) >= 2

        suit_count_with_card = board_suits.count(suit) + player_suits.count(suit)
        suit_improves_flush = suit_count_with_card >= 5

        if rank_improves_pairing or suit_improves_flush:
            contributing_cards += 1
            contribution_notes.append(card)

    # Straight contribution: if a straight exists using all cards, check whether
    # at least one hole-card rank is part of any 5-card straight window.
    all_values = sorted({_rank_value(r) for r in player_ranks + board_ranks})
    values_for_straight = set(all_values)
    if 14 in values_for_straight:
        values_for_straight.add(1)

    straight_values = set()
    for low in range(1, 11):
        window = set(range(low, low + 5))
        if window.issubset(values_for_straight):
            straight_values.update(window)

    for card in player_cards:
        value = _rank_value(_card_rank(card))
        ace_low_value = 1 if value == 14 else value

        if value in straight_values or ace_low_value in straight_values:
            if card not in contribution_notes:
                contributing_cards += 1
                contribution_notes.append(card)

    board_only_made_hand = contributing_cards == 0

    if board_only_made_hand:
        private_contribution = "private cards do not improve the board-made hand"
    elif contributing_cards == 1:
        private_contribution = f"one private card contributes: {contribution_notes}"
    else:
        private_contribution = f"both private cards contribute: {contribution_notes}"

    return {
        "hole_cards_used_count": contributing_cards,
        "board_only_made_hand": board_only_made_hand,
        "private_contribution": private_contribution,
    }

def _postflop_strength_bucket(hand_class_name, description, usage, community_cards):
    """
    Converts made hand + private-card usefulness into a strategy bucket.
    This is what the engine strategy should trust more than raw words like 'Pair'.
    """
    desc = description.upper()
    board_only = usage["board_only_made_hand"]
    hole_count = usage["hole_cards_used_count"]

    # Shared board-made hands are not real private strength.
    # Example: board has 3-3 and your hole cards do not improve it.
    if board_only and hand_class_name in ["Pair", "Three of a Kind", "Two Pair"]:
        return "WEAK_SHOWDOWN"

    if hand_class_name in ["Straight Flush", "Four of a Kind"]:
        return "NUT"

    if hand_class_name == "Full House":
        return "PREMIUM"

    if hand_class_name in ["Flush", "Straight"]:
        if board_only:
            return "MEDIUM"
        return "STRONG"

    if hand_class_name == "Three of a Kind":
        return "STRONG"

    if hand_class_name == "Two Pair":
        # Example: board Q-Q-8 and player has 4-4.
        # This is technically two pair, but vulnerable against any Qx.
        if "TWO PAIR" in desc and hole_count == 1:
            return "MEDIUM"

        if hole_count >= 1:
            return "MEDIUM_STRONG"

        return "WEAK_SHOWDOWN"

    if hand_class_name == "Pair":
        if any(x in desc for x in ["ACES", "KINGS", "QUEENS", "JACKS", "TENS"]):
            return "MEDIUM_STRONG"

        if any(x in desc for x in ["NINES", "EIGHTS", "SEVENS"]):
            return "MEDIUM"

        return "WEAK_SHOWDOWN"

    if hand_class_name == "High Card":
        return "WEAK"

    return "MEDIUM"

def evaluate_winners(players, community_cards):
    """Return all non-folded players tied for the best poker hand.

    Treys scores are lower for stronger hands. If multiple players have the
    same best score, they have exactly tied and should chop the pot.
    """
    evaluator = Evaluator()

    best_score = float("inf")
    best_players = []

    board = [convert_card(c) for c in community_cards]

    for player in players:
        if player.folded:
            continue

        hand = [convert_card(c) for c in player.cards]
        score = evaluator.evaluate(board, hand)

        if score < best_score:
            best_score = score
            best_players = [player]
        elif score == best_score:
            best_players.append(player)

    return best_players, best_score


def evaluate_winner(players, community_cards):
    """Backward-compatible wrapper returning the first best hand winner."""
    winners, best_score = evaluate_winners(players, community_cards)
    best_player = winners[0] if winners else None
    return best_player, best_score


def get_hand_summary(player_cards, community_cards):
    if len(community_cards) < 3:
        return _get_preflop_summary(player_cards)

    evaluator = Evaluator()

    board = [convert_card(c) for c in community_cards]
    hand = [convert_card(c) for c in player_cards]

    score = evaluator.evaluate(board, hand)
    hand_class = evaluator.get_rank_class(score)
    hand_class_name = evaluator.class_to_string(hand_class)

    all_cards = player_cards + community_cards
    description = _describe_made_hand(hand_class_name, all_cards)
    draws = _describe_draws(player_cards, community_cards)
    usage = _analyze_private_card_usage(player_cards, community_cards)
    strength_bucket = _postflop_strength_bucket(
        hand_class_name=hand_class_name,
        description=description,
        usage=usage,
        community_cards=community_cards,
    )

    can_improve = len(community_cards) < 5

    summary = (
        f"Verified current made hand category: {hand_class_name}. "
        f"Verified hand description: {description}. "
        f"Hand strength bucket: {strength_bucket}. "
        f"Hole cards used count: {usage['hole_cards_used_count']}. "
        f"Board-only made hand: {usage['board_only_made_hand']}. "
        f"Private-card contribution: {usage['private_contribution']}. "
        f"Private cards: {player_cards}. "
        f"Community cards: {community_cards}. "
    )

    if draws:
        summary += f"Verified current draws: {', '.join(draws)}. "
    else:
        summary += "Verified current draws: none. "

    if can_improve:
        summary += "Future cards remain, so the hand can still improve."
    else:
        summary += "This is the river. No future cards remain, so the hand cannot improve."

    return summary

def _describe_made_hand(hand_class_name, all_cards):
    ranks = [_card_rank(c) for c in all_cards]
    counts = {rank: ranks.count(rank) for rank in set(ranks)}

    pairs = [r for r, c in counts.items() if c == 2]
    trips = [r for r, c in counts.items() if c == 3]
    quads = [r for r, c in counts.items() if c == 4]

    pairs = sorted(pairs, key=_rank_value, reverse=True)
    trips = sorted(trips, key=_rank_value, reverse=True)
    quads = sorted(quads, key=_rank_value, reverse=True)

    if hand_class_name == "High Card":
        high = max(ranks, key=_rank_value)
        return f"{SINGULAR_RANK_NAMES[high]} high"

    if hand_class_name == "Pair":
        if pairs:
            return f"Pair of {RANK_NAMES[pairs[0]]}"
        return "One pair"

    if hand_class_name == "Two Pair":
        if len(pairs) >= 2:
            return f"Two pair: {RANK_NAMES[pairs[0]]} and {RANK_NAMES[pairs[1]]}"
        return "Two pair"

    if hand_class_name == "Three of a Kind":
        if trips:
            return f"Three of a kind: {RANK_NAMES[trips[0]]}"
        return "Three of a kind"

    if hand_class_name == "Straight":
        straight_high = _find_straight_high(ranks)
        if straight_high:
            return f"Straight, {SINGULAR_RANK_NAMES[straight_high]} high"
        return "Straight"

    if hand_class_name == "Flush":
        flush_suit = _find_flush_suit(all_cards)
        if flush_suit:
            flush_cards = [c for c in all_cards if _card_suit(c) == flush_suit]
            high = max([_card_rank(c) for c in flush_cards], key=_rank_value)
            return f"Flush, {SINGULAR_RANK_NAMES[high]} high"
        return "Flush"

    if hand_class_name == "Full House":
        if trips and pairs:
            return f"Full house: {RANK_NAMES[trips[0]]} full of {RANK_NAMES[pairs[0]]}"
        return "Full house"

    if hand_class_name == "Four of a Kind":
        if quads:
            return f"Four of a kind: {RANK_NAMES[quads[0]]}"
        return "Four of a kind"

    if hand_class_name == "Straight Flush":
        straight_high = _find_straight_high(ranks)
        if straight_high:
            return f"Straight flush, {SINGULAR_RANK_NAMES[straight_high]} high"
        return "Straight flush"

    return hand_class_name


def _find_straight_high(ranks):
    values = sorted({_rank_value(r) for r in ranks}, reverse=True)

    # Ace can also be low in A-2-3-4-5.
    if 14 in values:
        values.append(1)

    for high in range(14, 4, -1):
        needed = set(range(high - 4, high + 1))
        if needed.issubset(set(values)):
            if high == 5:
                return "5"
            for rank, value in zip(RANK_ORDER, range(2, 15)):
                if value == high:
                    return rank

    return None


def _find_flush_suit(all_cards):
    suits = [_card_suit(c) for c in all_cards]
    for suit in set(suits):
        if suits.count(suit) >= 5:
            return suit
    return None


def _describe_draws(player_cards, community_cards):
    # No draws on river.
    if len(community_cards) >= 5:
        return []

    all_cards = player_cards + community_cards
    draws = []

    suits = [_card_suit(c) for c in all_cards]
    for suit in set(suits):
        if suits.count(suit) == 4:
            draws.append("flush draw")

    ranks = [_card_rank(c) for c in all_cards]
    values = sorted({_rank_value(r) for r in ranks})

    if 14 in values:
        values.append(1)

    value_set = set(values)

    # Check 4-card straight windows.
    for low in range(1, 11):
        window = set(range(low, low + 5))
        have = len(window.intersection(value_set))

        if have == 4:
            draws.append("straight draw")
            break

    return draws


def _get_preflop_summary(player_cards):
    """Evaluate preflop hand strength based on hole cards."""
    card1, card2 = player_cards[0], player_cards[1]

    rank1 = card1[0]
    rank2 = card2[0]
    suit1 = card1[1]
    suit2 = card2[1]

    # Convert ranks to numbers for easier comparison
    rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    r1_val = rank_values.get(rank1, 0)
    r2_val = rank_values.get(rank2, 0)

    is_pair = rank1 == rank2
    is_suited = suit1 == suit2
    gap = abs(r1_val - r2_val)

    # Determine hand strength
    if is_pair:
        if r1_val >= 10:  # TT+
            strength = "PREMIUM (Pocket pair of high cards)"
        elif r1_val >= 8:  # 88-99
            strength = "STRONG (Mid-range pocket pair)"
        else:  # 22-77
            strength = "WEAK (Low pocket pair)"
    elif r1_val == 14 or r2_val == 14:  # Has an Ace
        kicker = r2_val if r1_val == 14 else r1_val
        if kicker == 13:  # AK
            strength = "PREMIUM (Ace-King)"
        elif kicker >= 11:  # AQ, AJ
            strength = "STRONG (Ace with high kicker)"
        elif kicker >= 9:  # AT, A9
            strength = "MEDIUM (Ace with medium kicker)"
        else:  # A2-A8
            strength = "WEAK (Ace with low kicker)"
    elif r1_val >= 12 or r2_val >= 12:  # Has K or Q
        if (r1_val >= 12 and r2_val >= 12):  # KK, QQ, KQ
            strength = "STRONG (High cards)"
        elif (r1_val >= 12 and r2_val >= 10) or (r2_val >= 12 and r1_val >= 10):  # K/Q with J or T
            strength = "MEDIUM (K/Q with decent kicker)"
        else:  # K/Q with low kicker
            strength = "WEAK (K/Q with low kicker)"
    elif is_suited and gap <= 3:  # Suited connectors or close cards
        strength = "MEDIUM (Suited with straight potential)"
    elif gap <= 2 and r1_val >= 9 and r2_val >= 9:  # High card connectors
        strength = "MEDIUM (High connectors with straight potential)"
    elif gap <= 3 and r1_val >= 10 and r2_val >= 10:  # High gap but high cards
        strength = "MEDIUM (High cards)"
    else:
        strength = "WEAK (Low cards with poor potential)"

    return f"PREFLOP ASSESSMENT: {strength}. Private cards: {player_cards}. Play according to hand strength."