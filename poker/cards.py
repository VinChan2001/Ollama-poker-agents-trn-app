import random

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]  # spades, hearts, diamonds, clubs


class Deck:
    def __init__(self):
        self.cards = [rank + suit for rank in RANKS for suit in SUITS]
        random.shuffle(self.cards)

    def deal(self, n=1):
        dealt = self.cards[:n]
        self.cards = self.cards[n:]
        return dealt