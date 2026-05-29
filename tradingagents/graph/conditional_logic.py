# TradingAgents/graph/conditional_logic.py

import re

from tradingagents.agents.utils.agent_states import AgentState


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1, debate_early_exit=True):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds
        self.debate_early_exit = debate_early_exit

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_market"
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if sentiment-analyst tool round should continue.

        Method name keeps the legacy ``social`` suffix to match the
        ``AnalystType.SOCIAL = "social"`` wire value (saved-config
        back-compat); the returned ``clear_node`` label uses the v0.2.5
        rename so it matches the node registered by the execution plan.
        """
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_social"
        return "Msg Clear Sentiment"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_news"
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools_fundamentals"
        return "Msg Clear Fundamentals"

    def _extract_direction(self, response_text: str) -> str | None:
        """Extract directional signal from a researcher's response text."""
        buy_pattern = re.compile(r'\b(BUY|BULL|BULLISH|LONG)\b', re.IGNORECASE)
        sell_pattern = re.compile(r'\b(SELL|BEAR|BEARISH|SHORT)\b', re.IGNORECASE)
        has_buy = buy_pattern.search(response_text) is not None
        has_sell = sell_pattern.search(response_text) is not None
        if has_buy and not has_sell:
            return "buy"
        if has_sell and not has_buy:
            return "sell"
        return None

    def _detect_consensus(self, state: AgentState) -> bool:
        """Detect if bull and bear agree on direction (both BUY or both SELL)."""
        debate_state = state.get("investment_debate_state", {})
        count = debate_state.get("count", 0)
        if count < 2:
            return False

        # last_response holds the previous round's response from the *other* agent;
        # current_response starts with "Bull" or "Bear" to indicate last speaker.
        last_response = debate_state.get("last_response", "")
        current_response = debate_state.get("current_response", "")

        if current_response.startswith("Bull"):
            bull_response, bear_response = current_response, last_response
        else:
            bull_response, bear_response = last_response, current_response

        bull_dir = self._extract_direction(bull_response)
        bear_dir = self._extract_direction(bear_response)
        return bull_dir is not None and bear_dir is not None and bull_dir == bear_dir

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # 3 rounds of back-and-forth between 2 agents
            return "Research Manager"
        if self.debate_early_exit and state["investment_debate_state"]["count"] >= 2:
            if self._detect_consensus(state):
                return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # 3 rounds of back-and-forth between 3 agents
            return "Portfolio Manager"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
