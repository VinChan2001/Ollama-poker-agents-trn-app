from queue import Queue
from threading import Thread

from poker.engine import PokerEngine
from poker.player import Player
from agents.ollama_agent import OllamaAgent


BLIND_LEVELS = [
    (10, 20),
    (15, 30),
    (25, 50),
    (50, 100),
    (75, 150),
    (100, 200),
    (150, 300),
    (250, 500),
    (500, 1000),
]


def build_players(starting_chips=1000):
    return [
        Player(name="Vin", chips=starting_chips),
        Player(name="Sam", chips=starting_chips),
        Player(name="Kai", chips=starting_chips),
        Player(name="Pap", chips=starting_chips),
        Player(name="Nik", chips=starting_chips),
    ]


def build_agents():
    return {
        "Vin": OllamaAgent(
            name="Vin",
            model="llama3.1:8b",
            personality=(
                "Table bully. Loud, fearless, and loves applying pressure. "
                "Raises strong hands aggressively and occasionally bluffs when opponents seem weak. "
                "Still respects huge all-ins and does not throw chips randomly."
            ),
        ),
        "Sam": OllamaAgent(
            name="Sam",
            model="qwen2.5:7b",
            personality=(
                "Math grinder. Obsessed with pot odds, stack sizes, and risk control. "
                "Usually tight and disciplined, but will snap-call if the price is good. "
                "Talks like every decision is a spreadsheet."
            ),
        ),
        "Kai": OllamaAgent(
            name="Kai",
            model="mistral:7b",
            personality=(
                "Smooth casino pro. Calm, balanced, and hard to read. "
                "Mixes value bets, traps, and occasional bluffs. "
                "Does not panic, does not overexplain, and prefers controlled aggression."
            ),
        ),
        "Pap": OllamaAgent(
            name="Pap",
            model="gemma2:9b",
            personality=(
                "Chaos merchant. Plays weird hands, loves seeing flops, and sometimes makes spicy raises. "
                "Can bluff with air, slow-play monsters, or call because the vibes feel cursed. "
                "Still must obey legal actions and should not go all-in every hand."
            ),
        ),
        "Nik": OllamaAgent(
            name="Nik",
            model="deepseek-r1:8b",
            personality=(
                "Silent assassin. Patient, analytical, and predatory. "
                "Folds boring spots, waits for leverage, then attacks weakness hard. "
                "Rarely bluffs, but when he does, it should make logical sense."
            ),
        ),
    }


def blind_level_for_hand(hand_number, hands_per_level=5):
    level_index = min((hand_number - 1) // hands_per_level, len(BLIND_LEVELS) - 1)
    return BLIND_LEVELS[level_index]


def print_chip_counts(players):
    for player in sorted(players, key=lambda p: p.chips, reverse=True):
        status = "OUT" if player.chips <= 0 else "IN"
        print(f"{player.name}: {player.chips} chips ({status})")


def _model_for_player(agents, player_name):
    agent = agents.get(player_name)
    return getattr(agent, "model", "unknown")


def _players_event_summary(players, agents, dealer_name=None, active_names=None):
    """Build a UI-safe snapshot of all tournament seats.

    PokerEngine only receives players who still have chips. The UI wants all five
    seats to remain visible, so tournament event generators decorate engine
    events with snapshots from the full player list.
    """
    active_name_set = set(active_names) if active_names is not None else None
    summaries = []

    for player in players:
        is_active_tournament_seat = (
            active_name_set is None
            or player.name in active_name_set
        )

        if not is_active_tournament_seat:
            status = "busted"
            cards = []
            folded = True
            current_bet = 0
            total_committed = 0
        else:
            cards = list(player.cards)
            folded = player.folded
            current_bet = player.current_bet
            total_committed = player.total_committed

            if player.folded:
                status = "folded"
            elif player.chips == 0:
                status = "all-in"
            else:
                status = "active"

        summaries.append(
            {
                "name": player.name,
                "model": _model_for_player(agents, player.name),
                "chips": player.chips,
                "cards": cards,
                "folded": folded,
                "current_bet": current_bet,
                "total_committed": total_committed,
                "status": status,
                "is_dealer": player.name == dealer_name,
            }
        )

    return summaries


def _build_event(
    event_type,
    players,
    agents,
    hand_number=0,
    street="preflop",
    pot=0,
    community_cards=None,
    dealer_name=None,
    active_names=None,
    run_mode="Full Tournament",
    **payload,
):
    return {
        "event_type": event_type,
        "run_mode": run_mode,
        "hand_number": hand_number,
        "street": street,
        "pot": pot,
        "community_cards": list(community_cards or []),
        "dealer": dealer_name,
        "players": _players_event_summary(
            players=players,
            agents=agents,
            dealer_name=dealer_name,
            active_names=active_names,
        ),
        "active_players": list(active_names or []),
        **payload,
    }


def _decorate_engine_event(event, players, agents, dealer_name, active_names, run_mode):
    decorated = dict(event)
    decorated["run_mode"] = run_mode
    decorated["dealer"] = event.get("dealer") or dealer_name
    decorated["players"] = _players_event_summary(
        players=players,
        agents=agents,
        dealer_name=decorated["dealer"],
        active_names=active_names,
    )
    decorated["active_players"] = list(active_names)
    return decorated


def run_single_hand_events(starting_chips=1000, small_blind=10, big_blind=20):
    """Yield structured events for one hand without changing CLI behavior."""
    players = build_players(starting_chips=starting_chips)
    agents = build_agents()
    active_names = [player.name for player in players]
    dealer_name = players[0].name

    yield _build_event(
        "single_hand_start",
        players=players,
        agents=agents,
        hand_number=1,
        dealer_name=dealer_name,
        active_names=active_names,
        run_mode="Single Hand",
        small_blind=small_blind,
        big_blind=big_blind,
    )
    yield _build_event(
        "blind_level",
        players=players,
        agents=agents,
        hand_number=1,
        dealer_name=dealer_name,
        active_names=active_names,
        run_mode="Single Hand",
        small_blind=small_blind,
        big_blind=big_blind,
        message=f"Blinds: {small_blind}/{big_blind}",
    )

    hand_events = []

    def collect_event(event):
        hand_events.append(
            _decorate_engine_event(
                event=event,
                players=players,
                agents=agents,
                dealer_name=dealer_name,
                active_names=active_names,
                run_mode="Single Hand",
            )
        )

    engine = PokerEngine(
        players,
        agents,
        event_callback=collect_event,
        hand_number=1,
        print_logs=False,
    )
    engine.state.small_blind = small_blind
    engine.state.big_blind = big_blind
    engine.state.min_raise = big_blind
    engine.play_hand()

    yield from hand_events


def run_single_hand_events_live(starting_chips=1000, small_blind=10, big_blind=20):
    """Yield single-hand events while the engine is still running."""
    event_queue = Queue()
    done = object()

    def worker():
        try:
            players = build_players(starting_chips=starting_chips)
            agents = build_agents()
            active_names = [player.name for player in players]
            dealer_name = players[0].name

            event_queue.put(
                _build_event(
                    "single_hand_start",
                    players=players,
                    agents=agents,
                    hand_number=1,
                    dealer_name=dealer_name,
                    active_names=active_names,
                    run_mode="Single Hand",
                    small_blind=small_blind,
                    big_blind=big_blind,
                )
            )
            event_queue.put(
                _build_event(
                    "blind_level",
                    players=players,
                    agents=agents,
                    hand_number=1,
                    dealer_name=dealer_name,
                    active_names=active_names,
                    run_mode="Single Hand",
                    small_blind=small_blind,
                    big_blind=big_blind,
                    message=f"Blinds: {small_blind}/{big_blind}",
                )
            )

            def collect_event(event):
                event_queue.put(
                    _decorate_engine_event(
                        event=event,
                        players=players,
                        agents=agents,
                        dealer_name=dealer_name,
                        active_names=active_names,
                        run_mode="Single Hand",
                    )
                )

            engine = PokerEngine(
                players,
                agents,
                event_callback=collect_event,
                hand_number=1,
                print_logs=False,
            )
            engine.state.small_blind = small_blind
            engine.state.big_blind = big_blind
            engine.state.min_raise = big_blind
            engine.play_hand()

        except Exception as exc:
            event_queue.put({"event_type": "error", "message": str(exc)})
        finally:
            event_queue.put(done)

    Thread(target=worker, daemon=True).start()

    while True:
        event = event_queue.get()
        if event is done:
            break
        yield event


def run_tournament_events(starting_chips=1000, hands_per_level=5, max_hands=300):
    """Yield structured events for the Streamlit tournament replay UI."""
    players = build_players(starting_chips=starting_chips)
    agents = build_agents()
    dealer_button_name = players[0].name
    hand_number = 1
    hand_results = []

    yield _build_event(
        "tournament_start",
        players=players,
        agents=agents,
        hand_number=0,
        dealer_name=dealer_button_name,
        active_names=[player.name for player in players],
        starting_chips=starting_chips,
        hands_per_level=hands_per_level,
        max_hands=max_hands,
        message="Tournament start",
    )

    while True:
        active_players = [player for player in players if player.chips > 0]
        active_names = [player.name for player in active_players]

        if len(active_players) == 1:
            champion = active_players[0]
            yield _build_event(
                "tournament_end",
                players=players,
                agents=agents,
                hand_number=hand_number - 1,
                dealer_name=dealer_button_name,
                active_names=active_names,
                winner=champion.name,
                winners=[champion.name],
                final_chips=champion.chips,
                hands_played=hand_number - 1,
                ended_by="single_winner",
                hand_results=hand_results,
                message=f"{champion.name} wins the tournament.",
            )
            return

        if hand_number > max_hands:
            leader = max(active_players, key=lambda player: player.chips)
            yield _build_event(
                "tournament_end",
                players=players,
                agents=agents,
                hand_number=hand_number - 1,
                dealer_name=dealer_button_name,
                active_names=active_names,
                winner=leader.name,
                winners=[leader.name],
                final_chips=leader.chips,
                hands_played=hand_number - 1,
                ended_by="max_hands_chip_leader",
                hand_results=hand_results,
                message=f"{leader.name} is the chip leader at max hands.",
            )
            return

        dealer_names = [player.name for player in active_players]
        if dealer_button_name not in dealer_names:
            dealer_index = 0
        else:
            dealer_index = dealer_names.index(dealer_button_name)

        dealer_name = active_players[dealer_index].name
        small_blind, big_blind = blind_level_for_hand(hand_number, hands_per_level)

        yield _build_event(
            "blind_level",
            players=players,
            agents=agents,
            hand_number=hand_number,
            dealer_name=dealer_name,
            active_names=active_names,
            small_blind=small_blind,
            big_blind=big_blind,
            message=f"Hand {hand_number}: blinds {small_blind}/{big_blind}",
        )

        hand_events = []

        def collect_event(event):
            hand_events.append(
                _decorate_engine_event(
                    event=event,
                    players=players,
                    agents=agents,
                    dealer_name=dealer_name,
                    active_names=active_names,
                    run_mode="Full Tournament",
                )
            )

        engine = PokerEngine(
            active_players,
            agents,
            event_callback=collect_event,
            hand_number=hand_number,
            print_logs=False,
        )
        engine.state.dealer_index = dealer_index
        engine.state.small_blind = small_blind
        engine.state.big_blind = big_blind
        engine.state.min_raise = big_blind

        result = engine.play_hand()
        hand_results.append(result)
        yield from hand_events

        eliminated_this_hand = [player for player in active_players if player.chips <= 0]
        surviving_names = [player.name for player in players if player.chips > 0]

        for player in eliminated_this_hand:
            yield _build_event(
                "player_busted",
                players=players,
                agents=agents,
                hand_number=hand_number,
                dealer_name=dealer_name,
                active_names=surviving_names,
                player=player.name,
                model=_model_for_player(agents, player.name),
                message=f"{player.name} is busted.",
            )

        yield _build_event(
            "leaderboard",
            players=players,
            agents=agents,
            hand_number=hand_number,
            dealer_name=dealer_name,
            active_names=surviving_names,
            leaderboard=[
                {"name": player.name, "chips": player.chips}
                for player in sorted(players, key=lambda player: player.chips, reverse=True)
            ],
            message=f"Hand {hand_number} complete.",
        )

        next_active = [player for player in players if player.chips > 0]
        if next_active:
            old_button_position = players.index(active_players[dealer_index])
            for offset in range(1, len(players) + 1):
                candidate = players[(old_button_position + offset) % len(players)]
                if candidate.chips > 0:
                    dealer_button_name = candidate.name
                    break

        hand_number += 1


def run_tournament_events_live(starting_chips=1000, hands_per_level=5, max_hands=300):
    """Yield tournament events live while local Ollama agents are deciding."""
    event_queue = Queue()
    done = object()

    def worker():
        try:
            players = build_players(starting_chips=starting_chips)
            agents = build_agents()
            dealer_button_name = players[0].name
            hand_number = 1
            hand_results = []

            event_queue.put(
                _build_event(
                    "tournament_start",
                    players=players,
                    agents=agents,
                    hand_number=0,
                    dealer_name=dealer_button_name,
                    active_names=[player.name for player in players],
                    starting_chips=starting_chips,
                    hands_per_level=hands_per_level,
                    max_hands=max_hands,
                    message="Tournament start",
                )
            )

            while True:
                active_players = [player for player in players if player.chips > 0]
                active_names = [player.name for player in active_players]

                if len(active_players) == 1:
                    champion = active_players[0]
                    event_queue.put(
                        _build_event(
                            "tournament_end",
                            players=players,
                            agents=agents,
                            hand_number=hand_number - 1,
                            dealer_name=dealer_button_name,
                            active_names=active_names,
                            winner=champion.name,
                            winners=[champion.name],
                            final_chips=champion.chips,
                            hands_played=hand_number - 1,
                            ended_by="single_winner",
                            hand_results=hand_results,
                            message=f"{champion.name} wins the tournament.",
                        )
                    )
                    return

                if hand_number > max_hands:
                    leader = max(active_players, key=lambda player: player.chips)
                    event_queue.put(
                        _build_event(
                            "tournament_end",
                            players=players,
                            agents=agents,
                            hand_number=hand_number - 1,
                            dealer_name=dealer_button_name,
                            active_names=active_names,
                            winner=leader.name,
                            winners=[leader.name],
                            final_chips=leader.chips,
                            hands_played=hand_number - 1,
                            ended_by="max_hands_chip_leader",
                            hand_results=hand_results,
                            message=f"{leader.name} is the chip leader at max hands.",
                        )
                    )
                    return

                dealer_names = [player.name for player in active_players]
                if dealer_button_name not in dealer_names:
                    dealer_index = 0
                else:
                    dealer_index = dealer_names.index(dealer_button_name)

                dealer_name = active_players[dealer_index].name
                small_blind, big_blind = blind_level_for_hand(hand_number, hands_per_level)

                event_queue.put(
                    _build_event(
                        "blind_level",
                        players=players,
                        agents=agents,
                        hand_number=hand_number,
                        dealer_name=dealer_name,
                        active_names=active_names,
                        small_blind=small_blind,
                        big_blind=big_blind,
                        message=f"Hand {hand_number}: blinds {small_blind}/{big_blind}",
                    )
                )

                def collect_event(event):
                    event_queue.put(
                        _decorate_engine_event(
                            event=event,
                            players=players,
                            agents=agents,
                            dealer_name=dealer_name,
                            active_names=active_names,
                            run_mode="Full Tournament",
                        )
                    )

                engine = PokerEngine(
                    active_players,
                    agents,
                    event_callback=collect_event,
                    hand_number=hand_number,
                    print_logs=False,
                )
                engine.state.dealer_index = dealer_index
                engine.state.small_blind = small_blind
                engine.state.big_blind = big_blind
                engine.state.min_raise = big_blind

                result = engine.play_hand()
                hand_results.append(result)

                eliminated_this_hand = [player for player in active_players if player.chips <= 0]
                surviving_names = [player.name for player in players if player.chips > 0]

                for player in eliminated_this_hand:
                    event_queue.put(
                        _build_event(
                            "player_busted",
                            players=players,
                            agents=agents,
                            hand_number=hand_number,
                            dealer_name=dealer_name,
                            active_names=surviving_names,
                            player=player.name,
                            model=_model_for_player(agents, player.name),
                            message=f"{player.name} is busted.",
                        )
                    )

                event_queue.put(
                    _build_event(
                        "leaderboard",
                        players=players,
                        agents=agents,
                        hand_number=hand_number,
                        dealer_name=dealer_name,
                        active_names=surviving_names,
                        leaderboard=[
                            {"name": player.name, "chips": player.chips}
                            for player in sorted(players, key=lambda player: player.chips, reverse=True)
                        ],
                        message=f"Hand {hand_number} complete.",
                    )
                )

                next_active = [player for player in players if player.chips > 0]
                if next_active:
                    old_button_position = players.index(active_players[dealer_index])
                    for offset in range(1, len(players) + 1):
                        candidate = players[(old_button_position + offset) % len(players)]
                        if candidate.chips > 0:
                            dealer_button_name = candidate.name
                            break

                hand_number += 1

        except Exception as exc:
            event_queue.put({"event_type": "error", "message": str(exc)})
        finally:
            event_queue.put(done)

    Thread(target=worker, daemon=True).start()

    while True:
        event = event_queue.get()
        if event is done:
            break
        yield event


def run_tournament(starting_chips=1000, hands_per_level=5, max_hands=300):
    players = build_players(starting_chips=starting_chips)
    agents = build_agents()
    dealer_button_name = players[0].name
    hand_number = 1
    hand_results = []

    print("==============================")
    print("TOURNAMENT START")
    print("==============================")
    print_chip_counts(players)

    while True:
        active_players = [player for player in players if player.chips > 0]

        if len(active_players) == 1:
            champion = active_players[0]
            print("\n==============================")
            print("TOURNAMENT WINNER")
            print("==============================")
            print(f"Winner: {champion.name}")
            print(f"Final chips: {champion.chips}")
            return {
                "winner": champion.name,
                "final_chips": champion.chips,
                "hands_played": hand_number - 1,
                "players": {player.name: player.chips for player in players},
                "hand_results": hand_results,
                "ended_by": "single_winner",
            }

        if hand_number > max_hands:
            # Safety valve so a local model loop cannot run forever.
            # In normal play, escalating blinds should produce one winner before this.
            leader = max(active_players, key=lambda player: player.chips)
            print("\n==============================")
            print("TOURNAMENT STOPPED AT MAX HANDS")
            print("==============================")
            print(f"Chip leader: {leader.name} with {leader.chips}")
            return {
                "winner": leader.name,
                "final_chips": leader.chips,
                "hands_played": hand_number - 1,
                "players": {player.name: player.chips for player in players},
                "hand_results": hand_results,
                "ended_by": "max_hands_chip_leader",
            }

        # Keep the dealer button as stable as possible across eliminations.
        dealer_names = [player.name for player in active_players]
        if dealer_button_name not in dealer_names:
            dealer_index = 0
        else:
            dealer_index = dealer_names.index(dealer_button_name)

        small_blind, big_blind = blind_level_for_hand(hand_number, hands_per_level)

        print("\n==============================")
        print(f"TOURNAMENT HAND #{hand_number}")
        print("==============================")
        print(f"Players: {', '.join(player.name for player in active_players)}")
        print(f"Dealer/Button: {active_players[dealer_index].name}")
        print(f"Blinds: {small_blind}/{big_blind}")
        print("\nChip counts before hand:")
        print_chip_counts(players)

        engine = PokerEngine(active_players, agents)
        engine.state.dealer_index = dealer_index
        engine.state.small_blind = small_blind
        engine.state.big_blind = big_blind
        engine.state.min_raise = big_blind

        result = engine.play_hand()
        hand_results.append(result)

        print("\n==============================")
        print(f"HAND #{hand_number} RESULT")
        print("==============================")
        print("Winner(s):", ", ".join(result.get("winners", [result["winner"]])))
        print("Pot:", result["pot"])
        print("Reason:", result["reason"])
        print("Community cards:", result["community_cards"])

        eliminated_this_hand = [player.name for player in active_players if player.chips <= 0]
        if eliminated_this_hand:
            print("Eliminated:", ", ".join(eliminated_this_hand))

        print("\nChip counts after hand:")
        print_chip_counts(players)

        # Move button to next surviving player after the current button.
        next_active = [player for player in players if player.chips > 0]
        if next_active:
            old_button_position = players.index(active_players[dealer_index])
            for offset in range(1, len(players) + 1):
                candidate = players[(old_button_position + offset) % len(players)]
                if candidate.chips > 0:
                    dealer_button_name = candidate.name
                    break

        hand_number += 1
