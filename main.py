from tournament import run_tournament


def main():
    # Runs a full tournament until only one player has chips left.
    # Blinds escalate every 5 hands so the tournament reaches one winner.
    run_tournament(starting_chips=300, hands_per_level=1, max_hands=12)


if __name__ == "__main__":
    main()
