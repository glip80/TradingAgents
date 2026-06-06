"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

import re

from tradingagents.agents.schemas import ResearchPlan, render_research_plan
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.report_summarizer import summarize_reports
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def _compress_debate_history(history: str) -> str:
    """Extract key arguments from each debate round, keeping first 1-2 sentences per speaker."""
    if not history or len(history) < 500:
        return history
    parts = re.split(r"(Bull Analyst:|Bear Analyst:)", history)
    compressed = []
    for i in range(0, len(parts) - 1, 2):
        speaker = parts[i]
        speech = parts[i + 1]
        sentences = re.split(r"(?<=[.!?])\s+", speech.strip())
        key_points = sentences[:2]
        compressed.append(f"{speaker} {' '.join(key_points)}")
    return " ".join(compressed)


def create_research_manager(llm):
    structured_llm = bind_structured(llm, ResearchPlan, "Research Manager")

    def research_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)
        history = state["investment_debate_state"].get("history", "")
        compressed_history = _compress_debate_history(history)

        market_research_report = state.get("market_summary") or summarize_reports(state)["market_summary"]
        sentiment_report = state.get("sentiment_summary") or summarize_reports(state)["sentiment_summary"]
        news_report = state.get("news_summary") or summarize_reports(state)["news_summary"]
        fundamentals_report = state.get("fundamentals_summary") or summarize_reports(state)["fundamentals_summary"]

        investment_debate_state = state["investment_debate_state"]

        prompt = f"""As the Research Manager and debate facilitator, your role is to critically evaluate this round of debate and deliver a clear, actionable investment plan for the trader.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction in the bull thesis; recommend taking or growing the position
- **Overweight**: Constructive view; recommend gradually increasing exposure
- **Hold**: Balanced view; recommend maintaining the current position
- **Underweight**: Cautious view; recommend trimming exposure
- **Sell**: Strong conviction in the bear thesis; recommend exiting or avoiding the position

Commit to a clear stance whenever the debate's strongest arguments warrant one; reserve Hold for situations where the evidence on both sides is genuinely balanced.

---

**Market Research Report:**
{market_research_report}

**Social Media Sentiment Report:**
{sentiment_report}

**Latest World Affairs Report:**
{news_report}

**Company Fundamentals Report:**
{fundamentals_report}

---

**Debate History (compressed):**
{compressed_history}""" + get_language_instruction()

        investment_plan = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_research_plan,
            "Research Manager",
        )

        new_investment_debate_state = {
            "judge_decision": investment_plan,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
