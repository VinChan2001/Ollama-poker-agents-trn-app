from dataclasses import dataclass, field
from poker.player import Player


@dataclass
class GameState:
    players: list[Player]
    dealer_index: int = 0
    small_blind: int = 10
    big_blind: int = 20

    pot: int = 0
    community_cards: list[str] = field(default_factory=list)
    current_bet: int = 0
    min_raise: int = 20
    street: str = "preflop"
    action_log: list[str] = field(default_factory=list)
    public_action_log: list[str] = field(default_factory=list)

    def active_players(self):
        return [p for p in self.players if not p.folded and p.chips > 0]

    def players_still_in_hand(self):
        return [p for p in self.players if not p.folded]