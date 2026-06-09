import json
import requests
from agents.base_agent import BaseAgent


class OllamaAgent(BaseAgent):
    def __init__(self, name, model, personality="balanced"):
        super().__init__(name)
        self.model = model
        self.personality = personality

    def decide(self, observation):
        prompt = self._build_prompt(observation)

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=180
            )

            response.raise_for_status()
            data = response.json()

            decision = json.loads(data["response"])

        except Exception as e:
            decision = {
                "action": "fold",
                "amount": 0,
                "reason": f"Ollama/model error, defaulted to fold: {e}"
            }

        return decision

    def _build_prompt(self, observation):
        return f"""
    You are {self.name}, a poker-playing AI agent.

    You are playing {observation["num_players"]}-player Texas Hold'em for study purposes only.
    There is no real money. These are only virtual chips.

    Your personality:
    {self.personality}

    You must choose exactly one legal action.

    PRIVATE INFORMATION:
    Your cards: {observation["your_cards"]}
    Your hand strength assessment: {observation["hand_summary"]}
    Strategic engine hint: {observation["strategy_hint"]}

    PUBLIC INFORMATION:
    Players still in hand: {observation["players_still_in_hand"]}
    Community cards: {observation["community_cards"]}
    Street: {observation["street"]}
    Pot: {observation["pot"]}
    Current table bet: {observation["current_bet"]}

    YOUR STATUS:
    Your chips: {observation["your_chips"]}
    Your current bet this round: {observation["your_current_bet"]}
    Call amount: {observation["call_amount"]}

    LEGAL ACTIONS:
    {observation["legal_actions"]}

    LEGAL ACTION EXPLANATIONS:
    {observation["legal_action_explanations"]}

    MINIMUM BET/RAISE AMOUNT:
    {observation["min_action_amount"]}

    RECENT ACTION LOG:
    {observation["public_action_log"]}

    Think briefly about:
    - your hand strength assessment (this is the source of truth for your actual card strength)
    - community cards
    - pot size
    - call amount
    - opponent actions

    CRITICAL RULES:
    - You must choose only one action from LEGAL ACTIONS.
    - If "check" is not listed in LEGAL ACTIONS, you cannot check.
    - If "call" is not listed in LEGAL ACTIONS, you cannot call.
    - If "bet" is not listed in LEGAL ACTIONS, you cannot bet.
    - If "raise" is not listed in LEGAL ACTIONS, you cannot raise.
    - ALWAYS use the hand strength assessment provided. This is the definitive evaluation of your cards.
    - NEVER invent or claim a different hand strength than what is provided in your hand strength assessment.
    - Your reason must be based on your hand strength, community cards, pot, call amount, and opponent actions.
    - Do not reveal or repeat your private cards in the reason. Keep private cards private until showdown.
    - In your reason, copy these values exactly from Strategic engine hint: call_pressure, hand_strength_bucket, board_only_made_hand, recommended_action_style.
    - Do not contradict Strategic engine hint. If call_amount is greater than 0, never claim call_pressure is NONE.
    - Do not say Board-only made hand is True unless hand_summary or strategy_hint explicitly says True.
    - Use Strategic engine hint as your main poker decision anchor.
    - Hand strength bucket is more important than the raw hand name.
    - Board-only made hand means your private cards do not improve the board-made hand. Treat this as weak showdown value, not a real strong hand.
    - If Board-only made hand is True, do not say "I have a strong pair/trips" unless strategy_hint says the bucket is STRONG or better.
    - If recommended_action_style contains DO_NOT_RAISE, RAISE_BAD, FOLD_PREFERRED, or FOLD_UNLESS_PREMIUM, do not raise.
    - If recommended_action_style says CALL_SMALL_ONLY_DO_NOT_RAISE, calling small bets is allowed, but raising is bad.
    - If recommended_action_style says CALL_OR_FOLD_RAISE_BAD, choose call or fold. Do not raise.
    - If call_pressure is LARGE, HUGE, or ALL_IN_CALL, one-pair or board-only hands should usually fold.
    - On paired boards, two pair can be vulnerable. Do not overplay weak two pair against heavy action.
    - Personality may affect aggression only when multiple actions are reasonable.
    - Do not make huge calls with weak or high-card hands unless the strategic hint says calling is reasonable.
    - Do not raise weak/high-card hands into multiple opponents unless the strategic hint allows semi-bluffing.
    - If call_pressure is HUGE or ALL_IN_CALL, continue only with premium made hands or very strong draws.
    - If recommended_action_style says FOLD_PREFERRED or FOLD_UNLESS_PREMIUM, you should usually fold.
    - If recommended_action_style says CHECK_PREFERRED, do not randomly bet just to be aggressive.
    - If recommended_action_style says CALL_OR_RAISE_FOR_VALUE, raising is allowed.
    - If recommended_action_style says VALUE_BET_ALLOWED, betting is allowed.
    - If recommended_action_style says VALUE_BET_SMALL_OR_CHECK or CHECK_OR_SMALL_VALUE_BET, keep aggression small.
    - You only know your own private cards.
    - You do NOT know opponents' private cards.
    - Never mention opponent private cards unless they were publicly revealed at showdown.
    - The recent action log contains only public information.
    - When explaining your hand, directly use the "Verified hand description" from hand_summary.
    - Do not say the board has no draws if hand_summary says there is a draw.
    - Do not name a specific pair rank, kicker, straight draw, flush draw, or opponent hand unless it is explicitly stated in hand_summary.
    - Never say "see the flop" after the flop has already been dealt.
    - Use the current Street value exactly.
    - Use hand_summary as the source of truth. Do not describe your hand differently from hand_summary.
    - On the river, there are no future cards. Never mention improving later, future cards, potential to improve, or observing further developments.
    - If recommended_action_style is FOLD_PREFERRED_BOARD_ONLY_HAND, you must fold unless fold is not legal.
    - Board-only trips are not a monster. If the trips are entirely on the board and you face LARGE, HUGE, or ALL_IN_CALL pressure, fold.
    - Do not call large river bets with board-only trips.
    - Do not say "no future cards remain" unless street is river.
    - On flop, two future cards remain.
    - On turn, one future card remains.
    - On river, no future cards remain.
    - If Board-only made hand is True, never describe the hand as MEDIUM, STRONG, PREMIUM, or NUT unless the hand_summary explicitly says that bucket.
    - Board-only pair and board-only trips are weak showdown value.
    - Street card counts: preflop has 0 community cards, flop has 3, turn has 4, river has 5.

    AMOUNT RULES:
    - If action is "fold", amount must be 0.
    - If action is "check", amount must be 0.
    - If action is "call", amount must equal call_amount.
    - If action is "bet", amount must be at least MINIMUM BET/RAISE AMOUNT.
    - If action is "raise", amount must be at least MINIMUM BET/RAISE AMOUNT.

    Return only valid JSON.
    Do not include markdown.
    Do not include text outside JSON.

    Required JSON format:

    {{
    "action": "choose exactly one from LEGAL ACTIONS",
    "amount": 0,
    "reason": "Use hand_summary and strategy_hint. Mention the current street, hand category, call pressure, and why this action fits."
    }}

    Example valid response:

    {{
    "action": "fold",
    "amount": 0,
    "reason": "WEAK hand strength assessment against aggressive opponent."
    }}
    """