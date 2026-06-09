class BaseAgent:
    def __init__(self, name):
        self.name = name

    def decide(self, observation):
        raise NotImplementedError("Each agent must implement decide()")