from dataclasses import dataclass, field

@dataclass

class Player:

    name: str

    chips: int = 1000

    cards: list[str] = field(default_factory=list)

    folded: bool = False

    current_bet: int = 0

    total_committed: int = 0

    def reset_for_new_hand(self):

        self.cards = []

        self.folded = False

        self.current_bet = 0

        self.total_committed = 0