from poker.cards import Deck
from poker.game_state import GameState
from poker.hand_eval import evaluate_winners, get_hand_summary


class PokerEngine:
    def __init__(self, players, agents, event_callback=None, hand_number=1, print_logs=True):
        self.state = GameState(players=players)
        self.agents = agents
        self.deck = None
        self.event_callback = event_callback
        self.hand_number = hand_number
        self.print_logs = print_logs

    def play_hand(self):
        self.state.dealer_index %= len(self.state.players)

        self._reset_hand()
        self._emit("hand_start")
        self._post_blinds()
        self._deal_hole_cards()

        self._print_street_heading("PREFLOP")
        self._emit("street_start", street="preflop")
        self._betting_round(start_index=self._preflop_start_index())

        if self._hand_over():
            return self._award_if_everyone_folded()

        self._print_street_heading("FLOP")
        self._deal_flop()
        self._betting_round(start_index=(self.state.dealer_index + 1) % len(self.state.players))

        if self._hand_over():
            return self._award_if_everyone_folded()

        self._print_street_heading("TURN")
        self._deal_turn()
        self._betting_round(start_index=(self.state.dealer_index + 1) % len(self.state.players))

        if self._hand_over():
            return self._award_if_everyone_folded()

        self._print_street_heading("RIVER")
        self._deal_river()
        self._betting_round(start_index=(self.state.dealer_index + 1) % len(self.state.players))

        if self._hand_over():
            return self._award_if_everyone_folded()

        return self._showdown()

    def _reset_hand(self):
        self.deck = Deck()

        self.state.pot = 0
        self.state.community_cards = []
        self.state.current_bet = 0
        self.state.min_raise = self.state.big_blind
        self.state.street = "preflop"
        self.state.action_log = []
        self.state.public_action_log = []

        for player in self.state.players:
            player.reset_for_new_hand()

    def _post_blinds(self):
        players = self.state.players

        if len(players) == 2:
            # Heads-up rule: dealer/button is the small blind.
            small_blind_index = self.state.dealer_index
            big_blind_index = (self.state.dealer_index + 1) % len(players)
        else:
            small_blind_index = (self.state.dealer_index + 1) % len(players)
            big_blind_index = (self.state.dealer_index + 2) % len(players)

        small_blind_player = players[small_blind_index]
        big_blind_player = players[big_blind_index]

        small_posted = self._commit_chips(small_blind_player, self.state.small_blind)
        big_posted = self._commit_chips(big_blind_player, self.state.big_blind)

        self.state.current_bet = max(small_blind_player.current_bet, big_blind_player.current_bet)
        self.state.min_raise = self.state.big_blind

        small_message = f"{small_blind_player.name} posts small blind {small_posted}"
        big_message = f"{big_blind_player.name} posts big blind {big_posted}"

        self._log(small_message)
        self._emit(
            "blind_posted",
            player=small_blind_player.name,
            model=self._model_for_player(small_blind_player.name),
            blind="small",
            action="small blind",
            amount=small_posted,
            message=small_message,
        )

        self._log(big_message)
        self._emit(
            "blind_posted",
            player=big_blind_player.name,
            model=self._model_for_player(big_blind_player.name),
            blind="big",
            action="big blind",
            amount=big_posted,
            message=big_message,
        )

    def _preflop_start_index(self):
        # Standard table: first action is under the gun, left of big blind.
        # Heads-up: small blind/button acts first preflop.
        if len(self.state.players) == 2:
            return self.state.dealer_index

        return (self.state.dealer_index + 3) % len(self.state.players)

    def _deal_hole_cards(self):
        for player in self.state.players:
            player.cards = self.deck.deal(2)

            # Private/debug log only. Do NOT show this to agents.
            self._log_private(f"{player.name} receives 2 private cards: {player.cards}")

        for card_index in range(2):
            for player in self.state.players:
                self._emit(
                    "deal_hole_card",
                    player=player.name,
                    model=self._model_for_player(player.name),
                    card=player.cards[card_index],
                    card_index=card_index + 1,
                )

        self._emit("private_cards_dealt")
        self._emit("reveal_hole_cards")

    def _deal_flop(self):
        self.state.street = "flop"
        self._reset_bets_for_new_street()
        self._emit("street_start", street="flop")

        flop_cards = self.deck.deal(3)
        for card_index, card in enumerate(flop_cards, start=1):
            self.state.community_cards.append(card)
            self._emit("deal_flop_card", card=card, card_index=card_index)

        self._log(f"Flop: {self.state.community_cards}")

    def _deal_turn(self):
        self.state.street = "turn"
        self._reset_bets_for_new_street()
        self._emit("street_start", street="turn")

        card = self.deck.deal(1)[0]
        self.state.community_cards.append(card)
        self._emit("deal_turn_card", card=card, card_index=4)
        self._log(f"Turn: {card}")

    def _deal_river(self):
        self.state.street = "river"
        self._reset_bets_for_new_street()
        self._emit("street_start", street="river")

        card = self.deck.deal(1)[0]
        self.state.community_cards.append(card)
        self._emit("deal_river_card", card=card, card_index=5)
        self._log(f"River: {card}")

    def _reset_bets_for_new_street(self):
        self.state.current_bet = 0
        self.state.min_raise = self.state.big_blind

        for player in self.state.players:
            player.current_bet = 0

    def _commit_chips(self, player, amount):
        amount = max(0, int(amount))
        amount = min(amount, player.chips)

        player.chips -= amount
        player.current_bet += amount
        player.total_committed += amount
        self.state.pot += amount

        return amount

    def _betting_round(self, start_index):
        players = self.state.players
        acted_since_last_aggressive_action = set()
        index = start_index

        while True:
            player = players[index]

            if not player.folded and player.chips > 0:
                observation = self._build_observation(player)
                agent = self.agents[player.name]

                self._emit(
                    "thinking",
                    player=player.name,
                    model=self._model_for_player(player.name),
                    legal_actions=observation["legal_actions"],
                    call_amount=observation["call_amount"],
                )

                decision = agent.decide(observation)
                decision = self._validate_decision(player, decision, observation)

                action_event = self._apply_decision(player, decision)
                action_event["legal_actions"] = observation["legal_actions"]
                action_event["call_amount"] = observation["call_amount"]
                self._emit("player_action", **action_event)

                # Bet or raise reopens action for the other players.
                if decision["action"] in ["bet", "raise"]:
                    acted_since_last_aggressive_action = {player.name}
                else:
                    acted_since_last_aggressive_action.add(player.name)

            if self._hand_over():
                break

            active_players = [
                p for p in players
                if not p.folded and p.chips > 0
            ]

            all_matched = all(
                p.chips == 0 or p.current_bet == self.state.current_bet
                for p in players
                if not p.folded
            )

            everyone_acted = all(
                p.name in acted_since_last_aggressive_action
                for p in active_players
            )

            if all_matched and everyone_acted:
                break

            index = (index + 1) % len(players)

    def _strategy_hint(self, player, call_amount, legal_actions, hand_summary):
        pot_after_call = self.state.pot + call_amount

        if call_amount == 0:
            pot_odds = 0.0
        else:
            pot_odds = call_amount / pot_after_call if pot_after_call > 0 else 1.0

        if player.chips <= 0:
            call_pressure = "ALL_IN"
        elif call_amount == 0:
            call_pressure = "NONE"
        elif call_amount >= player.chips:
            call_pressure = "ALL_IN_CALL"
        elif call_amount >= player.chips * 0.50:
            call_pressure = "HUGE"
        elif call_amount >= player.chips * 0.25:
            call_pressure = "LARGE"
        elif call_amount >= player.chips * 0.10:
            call_pressure = "MEDIUM"
        else:
            call_pressure = "SMALL"

        summary_upper = hand_summary.upper()

        board_only = "BOARD-ONLY MADE HAND: TRUE" in summary_upper

        # Exact bucket parsing.
        # Do NOT use substring matching because:
        # MEDIUM_STRONG contains MEDIUM/STRONG,
        # WEAK_SHOWDOWN contains WEAK.
        bucket = "UNKNOWN"
        marker = "HAND STRENGTH BUCKET:"

        if marker in summary_upper:
            bucket = summary_upper.split(marker, 1)[1].split(".", 1)[0].strip()

        is_nut = bucket == "NUT"
        is_premium = bucket == "PREMIUM"
        is_strong = bucket == "STRONG"
        is_medium_strong = bucket == "MEDIUM_STRONG"
        is_medium = bucket == "MEDIUM"
        is_weak_showdown = bucket == "WEAK_SHOWDOWN"
        is_weak = bucket == "WEAK"

        has_draw = "FLUSH DRAW" in summary_upper or "STRAIGHT DRAW" in summary_upper

        is_dangerous_pressure = call_pressure in ["LARGE", "HUGE", "ALL_IN_CALL"]

        # No bet to call: choose whether to check or bet.
        if call_amount == 0:
            if is_nut or is_premium:
                recommended = "VALUE_BET_ALLOWED"
            elif is_strong:
                recommended = "VALUE_BET_SMALL_OR_CHECK"
            elif is_medium_strong:
                recommended = "CHECK_OR_SMALL_VALUE_BET"
            elif has_draw:
                recommended = "CHECK_OR_SEMI_BLUFF_SMALL"
            else:
                recommended = "CHECK_PREFERRED"

        # Facing a bet.
        else:
            if board_only and is_dangerous_pressure:
                recommended = "FOLD_PREFERRED_BOARD_ONLY_HAND"

            elif is_nut or is_premium:
                recommended = "CALL_OR_RAISE_FOR_VALUE"

            elif is_strong:
                if call_pressure in ["SMALL", "MEDIUM"]:
                    recommended = "CALL_OR_RAISE_SMALL_FOR_VALUE"
                else:
                    recommended = "CALL_PREFERRED_RAISE_DISCOURAGED"

            elif is_medium_strong:
                if call_pressure in ["SMALL", "MEDIUM"]:
                    recommended = "CALL_PREFERRED_RAISE_DISCOURAGED"
                else:
                    recommended = "CALL_OR_FOLD_RAISE_BAD"

            elif is_medium:
                if board_only:
                    if call_pressure == "SMALL" and pot_odds <= 0.20:
                        recommended = "CALL_SMALL_ONLY_DO_NOT_RAISE"
                    else:
                        recommended = "FOLD_PREFERRED_BOARD_ONLY_HAND"
                elif call_pressure in ["SMALL", "MEDIUM"]:
                    recommended = "CALL_PREFERRED_RAISE_DISCOURAGED"
                else:
                    recommended = "CALL_OR_FOLD_RAISE_BAD"

            elif has_draw and call_pressure in ["SMALL", "MEDIUM"]:
                recommended = "CALL_IF_PRICE_IS_REASONABLE"

            elif is_weak_showdown:
                if self.state.street == "river":
                    if call_pressure == "SMALL" and pot_odds <= 0.10:
                        recommended = "CALL_SMALL_ONLY_DO_NOT_RAISE"
                    else:
                        recommended = "FOLD_PREFERRED"
                else:
                    if call_pressure == "SMALL" and pot_odds <= 0.15:
                        recommended = "CALL_SMALL_ONLY_DO_NOT_RAISE"
                    else:
                        recommended = "FOLD_PREFERRED"

            elif is_weak:
                if call_pressure == "SMALL" and pot_odds <= 0.15:
                    recommended = "CALL_OR_FOLD_DEPENDING_ON_PERSONALITY"
                else:
                    recommended = "FOLD_PREFERRED"

            elif is_dangerous_pressure:
                recommended = "FOLD_UNLESS_PREMIUM"

            else:
                recommended = "CALL_OR_FOLD_DEPENDING_ON_PERSONALITY"

        return {
            "pot_odds": round(pot_odds, 3),
            "pot_odds_explanation": "call_amount / (pot + call_amount); lower is cheaper",
            "call_pressure": call_pressure,
            "hand_strength_bucket": bucket,
            "board_only_made_hand": board_only,
            "recommended_action_style": recommended,
        }

    def _board_suit_counts(self):
        counts = {}

        for card in self.state.community_cards:
            suit = card[-1]
            counts[suit] = counts.get(suit, 0) + 1

        return counts

    def _board_has_four_flush_cards(self):
        return any(count >= 4 for count in self._board_suit_counts().values())

    def _player_has_flush(self, player):
        all_cards = player.cards + self.state.community_cards
        counts = {}

        for card in all_cards:
            suit = card[-1]
            counts[suit] = counts.get(suit, 0) + 1

        return any(count >= 5 for count in counts.values())

    def _build_observation(self, player):
        call_amount = max(0, self.state.current_bet - player.current_bet)

        legal_actions = []

        if call_amount == 0:
            legal_actions.append("check")

            if player.chips >= self.state.min_raise:
                # If current_bet is 0, nobody has bet on this street yet -> bet.
                # If current_bet > 0, player has already matched the bet/blind -> raise.
                if self.state.current_bet == 0:
                    legal_actions.append("bet")
                else:
                    legal_actions.append("raise")

        else:
            legal_actions.append("fold")

            # Calling is legal even if player has fewer chips than call_amount.
            # In that case, _commit_chips() turns it into an all-in call.
            if player.chips > 0:
                legal_actions.append("call")

            if player.chips >= call_amount + self.state.min_raise:
                legal_actions.append("raise")

        hand_summary = get_hand_summary(player.cards, self.state.community_cards)

        strategy_hint = self._strategy_hint(
            player=player,
            call_amount=call_amount,
            legal_actions=legal_actions,
            hand_summary=hand_summary,
        )

        return {
            "player_name": player.name,
            "your_cards": player.cards,
            "community_cards": self.state.community_cards,
            "street": self.state.street,
            "pot": self.state.pot,
            "your_chips": player.chips,
            "current_bet": self.state.current_bet,
            "your_current_bet": player.current_bet,
            "call_amount": call_amount,
            "num_players": len(self.state.players),
            "players_still_in_hand": [p.name for p in self.state.players if not p.folded],
            "legal_actions": legal_actions,
            "hand_summary": hand_summary,
            "strategy_hint": strategy_hint,
            "legal_action_explanations": self._legal_action_explanations(legal_actions, call_amount),
            "min_action_amount": call_amount + self.state.min_raise,
            "public_action_log": self.state.public_action_log[-12:],
        }

    def _legal_action_explanations(self, legal_actions, call_amount):
        explanations = {}

        if "fold" in legal_actions:
            explanations["fold"] = "Give up this hand and commit no more chips."

        if "check" in legal_actions:
            explanations["check"] = "Continue without adding chips. Only legal when call_amount is 0."

        if "call" in legal_actions:
            explanations["call"] = f"Match the current bet by adding exactly {call_amount} chips."

        if "bet" in legal_actions:
            explanations["bet"] = "Start betting on this street. Legal only when nobody has bet yet."

        if "raise" in legal_actions:
            explanations["raise"] = (
                "Add chips to increase the current table bet. "
                "This can happen after another bet or after you have already matched the blind."
            )

        return explanations

    def _validate_decision(self, player, decision, observation):
        legal_actions = observation["legal_actions"]

        action = decision.get("action", "fold")
        amount = decision.get("amount", 0)
        reason = decision.get("reason", "No reason provided.")

        try:
            amount = int(amount)
        except Exception:
            amount = 0

        hint = observation.get("strategy_hint", {})
        style = hint.get("recommended_action_style", "")

        # Hard safety rail: the model must not continue with board-only trash
        # when the deterministic strategy engine says to fold.
        if (
            action in ["call", "raise", "bet"]
            and style == "FOLD_PREFERRED_BOARD_ONLY_HAND"
            and "fold" in legal_actions
        ):
            return {
                "action": "fold",
                "amount": 0,
                "reason": (
                    "Engine override: strategy_hint recommended "
                    "FOLD_PREFERRED_BOARD_ONLY_HAND, so this board-only made hand "
                    "must fold instead of continuing."
                ),
            }

        bucket = hint.get("hand_strength_bucket", "")
        board_only = bool(hint.get("board_only_made_hand", False))
        call_pressure = hint.get("call_pressure", "")
        call_amount = observation.get("call_amount", 0)
        street = observation.get("street", self.state.street)
        player_has_flush = self._player_has_flush(player)
        river_four_flush = street == "river" and self._board_has_four_flush_cards()

        # Hard safety rail: if strategy says raising is discouraged, never let the
        # LLM convert a call spot into a raise. Convert the raise into a normal call.
        if (
            action == "raise"
            and style in [
                "CALL_PREFERRED_RAISE_DISCOURAGED",
                "CALL_IF_PRICE_IS_REASONABLE",
                "CALL_SMALL_ONLY_DO_NOT_RAISE",
                "CALL_OR_FOLD_RAISE_BAD",
            ]
            and "call" in legal_actions
        ):
            return {
                "action": "call",
                "amount": call_amount,
                "reason": (
                    "Engine override: strategy_hint discouraged raising, "
                    "so the raise was corrected to a call."
                ),
            }

        # Hard safety rail: medium-or-worse river hands should not continue
        # against large/huge pressure. The LLM often talks itself into crying calls.
        if (
            action in ["call", "raise"]
            and street == "river"
            and call_pressure in ["LARGE", "HUGE", "ALL_IN_CALL"]
            and bucket in ["WEAK", "WEAK_SHOWDOWN", "MEDIUM"]
            and "fold" in legal_actions
        ):
            return {
                "action": "fold",
                "amount": 0,
                "reason": (
                    "Engine override: medium-or-worse river hand facing "
                    "large/huge pressure was corrected to fold."
                ),
            }

        # Hard safety rail: when the river board has four cards of one suit,
        # non-flush hands should not raise into action. Trips/two pair look strong
        # in isolation but are fragile on this texture.
        if (
            river_four_flush
            and not player_has_flush
            and action in ["bet", "raise"]
            and bucket in ["MEDIUM", "MEDIUM_STRONG", "STRONG"]
        ):
            if "call" in legal_actions:
                return {
                    "action": "call",
                    "amount": call_amount,
                    "reason": (
                        "Engine override: river board has four cards of one suit, "
                        "so a non-flush made hand was not allowed to raise."
                    ),
                }

            if "check" in legal_actions:
                return {
                    "action": "check",
                    "amount": 0,
                    "reason": (
                        "Engine override: river board has four cards of one suit, "
                        "so a non-flush made hand was not allowed to bet."
                    ),
                }

        # Hard safety rail: when the deterministic strategy says FOLD_PREFERRED,
        # do not allow the LLM to "personality-call" anyway. This catches
        # weak board-only pair/trips/two-pair calls when the price is not good enough.
        if (
            action in ["call", "raise", "bet"]
            and style == "FOLD_PREFERRED"
            and "fold" in legal_actions
        ):
            return {
                "action": "fold",
                "amount": 0,
                "reason": (
                    "Engine override: strategy_hint recommended FOLD_PREFERRED, "
                    "so the action was corrected to fold instead of continuing."
                ),
            }

        # Hard safety rail: board-only WEAK_SHOWDOWN hands should not call bets
        # unless strategy_hint explicitly says a tiny call is acceptable.
        if (
            action in ["call", "raise", "bet"]
            and board_only
            and bucket in ["WEAK", "WEAK_SHOWDOWN"]
            and style not in ["CALL_SMALL_ONLY_DO_NOT_RAISE", "CALL_IF_PRICE_IS_REASONABLE"]
            and "fold" in legal_actions
        ):
            return {
                "action": "fold",
                "amount": 0,
                "reason": (
                    "Engine override: board-only weak showdown hand did not have "
                    "an explicit small-call strategy, so the action was corrected to fold."
                ),
            }

        # Hard safety rail: do not let the model turn shared weak board texture
        # into fake value bets just because betting is technically legal.
        if (
            action in ["bet", "raise"]
            and "check" in legal_actions
            and (
                style == "CHECK_PREFERRED"
                or (board_only and bucket in ["WEAK", "WEAK_SHOWDOWN", "MEDIUM"])
            )
        ):
            return {
                "action": "check",
                "amount": 0,
                "reason": (
                    "Engine override: strategy_hint did not allow aggression with "
                    "this weak/shared hand, so the action was corrected to check."
                ),
            }

        # If the model picks an illegal action, do a controlled correction.
        # Specific natural corrections are allowed.
        # Unknown garbage actions should usually fold instead of accidentally calling huge bets.
        if action not in legal_actions:
            original_action = action

            # Model said "check", but there is a bet to respond to.
            # In poker, check is illegal here. Calling is the closest natural correction.
            if original_action == "check" and "call" in legal_actions:
                return {
                    "action": "call",
                    "amount": observation["call_amount"],
                    "reason": (
                        f"Invalid model action 'check', corrected to call because "
                        f"there is a bet to match. Original reason: {reason}"
                    ),
                }

            # Model said "call", but there is no bet to call.
            # In poker, this should become check.
            if original_action == "call" and "check" in legal_actions:
                return {
                    "action": "check",
                    "amount": 0,
                    "reason": (
                        f"Invalid model action 'call', corrected to check because "
                        f"there is no bet to call. Original reason: {reason}"
                    ),
                }

            # Model said "raise", but nobody has bet yet.
            # Closest correction is bet.
            if original_action == "raise" and "bet" in legal_actions:
                return {
                    "action": "bet",
                    "amount": self.state.min_raise,
                    "reason": (
                        f"Invalid model action 'raise', corrected to bet because "
                        f"nobody has bet yet on this street. Original reason: {reason}"
                    ),
                }

            # Model said "bet", but the correct aggressive action is raise.
            if original_action == "bet" and "raise" in legal_actions:
                return {
                    "action": "raise",
                    "amount": observation["min_action_amount"],
                    "reason": (
                        f"Invalid model action 'bet', corrected to raise because "
                        f"a bet/blind already exists. Original reason: {reason}"
                    ),
                }

            # Model said "bet", but only calling is available.
            if original_action == "bet" and "call" in legal_actions:
                return {
                    "action": "call",
                    "amount": observation["call_amount"],
                    "reason": (
                        f"Invalid model action 'bet', corrected to call because "
                        f"raising is not available. Original reason: {reason}"
                    ),
                }

            # If checking is legal, use check as safe fallback.
            if "check" in legal_actions:
                return {
                    "action": "check",
                    "amount": 0,
                    "reason": (
                        f"Invalid model action '{original_action}', corrected to check. "
                        f"Original reason: {reason}"
                    ),
                }

            # If folding is legal, prefer fold as the safe fallback.
            # Do not accidentally call huge bets because the model returned nonsense.
            if "fold" in legal_actions:
                return {
                    "action": "fold",
                    "amount": 0,
                    "reason": (
                        f"Invalid model action '{original_action}', corrected to fold. "
                        f"Original reason: {reason}"
                    ),
                }

            # Very rare fallback.
            if "call" in legal_actions:
                return {
                    "action": "call",
                    "amount": observation["call_amount"],
                    "reason": (
                        f"Invalid model action '{original_action}', corrected to call. "
                        f"Original reason: {reason}"
                    ),
                }

            return {
                "action": "fold",
                "amount": 0,
                "reason": (
                    f"Invalid model action '{original_action}', corrected to fold. "
                    f"Original reason: {reason}"
                ),
            }

        if action == "fold":
            amount = 0

        elif action == "check":
            amount = 0

        elif action == "call":
            amount = observation["call_amount"]

        elif action == "bet":
            minimum = self.state.min_raise

            # If the model gives a weird tiny value with a strong value-bet hint,
            # size it to a reasonable default.
            hint = observation.get("strategy_hint", {})
            style = hint.get("recommended_action_style", "")

            if amount <= minimum and "VALUE" in style:
                amount = max(minimum, int(self.state.pot * 0.50))

            amount = max(amount, minimum)
            amount = min(amount, player.chips)

        elif action == "raise":
            minimum = observation["min_action_amount"]

            hint = observation.get("strategy_hint", {})
            style = hint.get("recommended_action_style", "")

            if amount <= minimum and "VALUE" in style:
                amount = max(
                    minimum,
                    observation["call_amount"] + int(self.state.pot * 0.50),
                )

            amount = max(amount, minimum)
            amount = min(amount, player.chips)

        return {
            "action": action,
            "amount": amount,
            "reason": reason,
        }

    def _apply_decision(self, player, decision):
        action = decision["action"]
        amount = decision["amount"]
        reason = decision["reason"]
        committed = 0

        if action == "fold":
            player.folded = True
            public_message = f"{player.name} folds."
            self._log_action(
                public_message=public_message,
                debug_message=f"{player.name} folds. Reason: {reason}",
            )

        elif action == "check":
            public_message = f"{player.name} checks."
            self._log_action(
                public_message=public_message,
                debug_message=f"{player.name} checks. Reason: {reason}",
            )

        elif action == "call":
            committed = self._commit_chips(player, amount)
            all_in_text = " all-in" if player.chips == 0 else ""
            public_message = f"{player.name} calls{all_in_text} {committed}."
            self._log_action(
                public_message=public_message,
                debug_message=f"{player.name} calls{all_in_text} {committed}. Reason: {reason}",
            )

        elif action == "bet":
            previous_bet = self.state.current_bet

            committed = self._commit_chips(player, amount)

            self.state.current_bet = player.current_bet
            self.state.min_raise = max(
                self.state.big_blind,
                self.state.current_bet - previous_bet,
            )

            all_in_text = " all-in" if player.chips == 0 else ""
            public_message = f"{player.name} bets{all_in_text} {committed}."
            self._log_action(
                public_message=public_message,
                debug_message=f"{player.name} bets{all_in_text} {committed}. Reason: {reason}",
            )

        elif action == "raise":
            previous_bet = self.state.current_bet

            committed = self._commit_chips(player, amount)

            self.state.current_bet = player.current_bet
            self.state.min_raise = max(
                self.state.big_blind,
                self.state.current_bet - previous_bet,
            )

            all_in_text = " all-in" if player.chips == 0 else ""
            public_message = f"{player.name} raises{all_in_text} by {committed} to {player.current_bet}."
            self._log_action(
                public_message=public_message,
                debug_message=(
                    f"{player.name} raises{all_in_text} by {committed} "
                    f"to {player.current_bet}. Reason: {reason}"
                ),
            )

        return {
            "player": player.name,
            "model": self._model_for_player(player.name),
            "action": action,
            "amount": committed,
            "declared_amount": amount,
            "reason": reason,
            "message": public_message,
            "all_in": player.chips == 0,
            "player_current_bet": player.current_bet,
            "table_current_bet": self.state.current_bet,
        }

    def _hand_over(self):
        return len(self.state.players_still_in_hand()) == 1

    def _award_if_everyone_folded(self):
        winner = self.state.players_still_in_hand()[0]
        pot_amount = self.state.pot
        winner.chips += pot_amount

        message = f"{winner.name} wins pot of {pot_amount}. Everyone else folded."
        self._log(message)

        result = {
            "winner": winner.name,
            "winners": [winner.name],
            "pot": pot_amount,
            "reason": "Everyone else folded.",
            "community_cards": self.state.community_cards,
            "players": self._players_summary(),
            "action_log": self.state.public_action_log,
            "debug_log": self.state.action_log,
        }

        self._emit(
            "hand_end",
            winner=winner.name,
            winners=[winner.name],
            reason=result["reason"],
            message=message,
            result=result,
        )
        return result

    def _showdown(self):
        self.state.street = "showdown"
        remaining_players = self.state.players_still_in_hand()
        winners, score = evaluate_winners(remaining_players, self.state.community_cards)

        pot_amount = self.state.pot
        base_share = pot_amount // len(winners)
        odd_chips = pot_amount % len(winners)

        # Odd chip goes to the earliest tied winner in table order.
        table_ordered_winners = [p for p in self.state.players if p in winners]

        for index, winner in enumerate(table_ordered_winners):
            share = base_share + (1 if index < odd_chips else 0)
            winner.chips += share

        self._log("Showdown reached.")

        if len(table_ordered_winners) == 1:
            message = f"{table_ordered_winners[0].name} wins pot of {pot_amount}."
            self._log(message)
        else:
            split_details = ", ".join(
                f"{winner.name} receives {base_share + (1 if index < odd_chips else 0)}"
                for index, winner in enumerate(table_ordered_winners)
            )
            winner_names = ", ".join(winner.name for winner in table_ordered_winners)
            message = f"{winner_names} split pot of {pot_amount}. {split_details}."
            self._log(message)

        result = {
            "winner": table_ordered_winners[0].name,
            "winners": [winner.name for winner in table_ordered_winners],
            "pot": pot_amount,
            "reason": "Best poker hand at showdown.",
            "community_cards": self.state.community_cards,
            "players": self._players_summary(),
            "action_log": self.state.public_action_log,
            "debug_log": self.state.action_log,
        }

        self._emit(
            "showdown",
            winner=result["winner"],
            winners=result["winners"],
            score=score,
            reason=result["reason"],
            message="Showdown reached.",
            result=result,
        )
        self._emit(
            "hand_end",
            winner=result["winner"],
            winners=result["winners"],
            reason=result["reason"],
            message=message,
            result=result,
        )
        return result

    def _players_summary(self):
        return {
            p.name: {
                "cards": p.cards,
                "chips": p.chips,
                "folded": p.folded,
                "current_bet": p.current_bet,
                "total_committed": p.total_committed,
            }
            for p in self.state.players
        }

    def _log_action(self, public_message, debug_message):
        """Log action publicly without private-card/reason leakage.

        Agent reasons can contain their private cards or hallucinated strategy text,
        so only the sanitized public action goes into public_action_log. The full
        reason stays in action_log/debug_log for post-hand inspection.
        """
        self.state.public_action_log.append(public_message)
        self.state.action_log.append(debug_message)
        if self.print_logs:
            print(debug_message)

    def _log(self, message):
        self.state.action_log.append(message)
        self.state.public_action_log.append(message)
        if self.print_logs:
            print(message)

    def _log_private(self, message):
        self.state.action_log.append(message)
        if self.print_logs:
            print(message)

    def _print_street_heading(self, street):
        if self.print_logs:
            print(f"\n=== {street} ===")

    def _model_for_player(self, player_name):
        agent = self.agents.get(player_name)
        return getattr(agent, "model", "unknown")

    def _player_status(self, player):
        if player.folded:
            return "folded"
        if player.chips == 0:
            return "all-in"
        return "active"

    def _players_event_summary(self):
        players = []

        for index, player in enumerate(self.state.players):
            players.append(
                {
                    "name": player.name,
                    "model": self._model_for_player(player.name),
                    "chips": player.chips,
                    "cards": list(player.cards),
                    "folded": player.folded,
                    "current_bet": player.current_bet,
                    "total_committed": player.total_committed,
                    "status": self._player_status(player),
                    "is_dealer": index == self.state.dealer_index,
                }
            )

        return players

    def _emit(self, event_type, **payload):
        if not self.event_callback:
            return

        dealer = None
        if self.state.players:
            dealer = self.state.players[self.state.dealer_index].name

        event = {
            "event_type": event_type,
            "hand_number": self.hand_number,
            "street": payload.pop("street", self.state.street),
            "pot": self.state.pot,
            "community_cards": list(self.state.community_cards),
            "small_blind": self.state.small_blind,
            "big_blind": self.state.big_blind,
            "dealer": dealer,
            "players": self._players_event_summary(),
            "public_action_log": list(self.state.public_action_log),
        }
        event.update(payload)
        self.event_callback(event)
