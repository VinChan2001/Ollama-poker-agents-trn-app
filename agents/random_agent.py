import random
from agents.base_agent import BaseAgent


class RandomAgent(BaseAgent):
    def decide(self, observation):
        legal_actions = observation["legal_actions"]
        action = random.choice(legal_actions)

        if action == "bet":
            amount = observation["min_action_amount"]

        elif action == "raise":
            amount = observation["min_action_amount"]

        elif action == "call":
            amount = observation["call_amount"]

        else:
            amount = 0

        return {
            "action": action,
            "amount": amount,
            "reason": "Random test decision."
        }
