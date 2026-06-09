from poker.engine import PokerEngine
from tournament import build_agents, build_players


def main():
    players = build_players(starting_chips=1000)
    agents = build_agents()
    engine = PokerEngine(players, agents)
    result = engine.play_hand()

    print("\n==============================")
    print("FINAL RESULT")
    print("==============================")
    print("Winner:", result["winner"])
    print("Pot:", result["pot"])
    print("Reason:", result["reason"])
    print("Community cards:", result["community_cards"])

    print("\n==============================")
    print("PLAYERS")
    print("==============================")
    for name, info in result["players"].items():
        print(name)
        print("  Cards:", info["cards"])
        print("  Chips:", info["chips"])
        print("  Folded:", info["folded"])
        print("  Total committed:", info["total_committed"])

    print("\n==============================")
    print("ACTION LOG")
    print("==============================")
    for action in result["action_log"]:
        print(action)

    print("\n==============================")
    print("DEBUG LOG")
    print("==============================")
    for action in result["debug_log"]:
        print(action)


if __name__ == "__main__":
    main()
