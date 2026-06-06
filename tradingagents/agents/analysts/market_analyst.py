from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_indicators,
    get_language_instruction,
    get_stock_data,
    get_verified_market_snapshot,
)
from tradingagents.dataflows.config import get_config


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)

        tools = [
            get_stock_data,
            get_indicators,
            get_verified_market_snapshot,
        ]

        system_message = (
            """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

Moving Averages (TA-Lib):
- close_50_sma (50 SMA): medium-term trend, dynamic support/resistance.
- close_200_sma (200 SMA): long-term trend benchmark, golden/death cross setups.
- close_10_ema (10 EMA): responsive short-term momentum, entry signals.
- SMA3, SMA50, SMA200, EMA6, EMA12: additional moving averages via get_indicators()

MACD Related (TA-Lib):
- macd (MACD): momentum via EMA differences, crossover/divergence signals.
- macds (MACD Signal): EMA of MACD line, crossover trade triggers.
- macdh (MACD Histogram): MACD-signal gap, momentum strength visualization.

Momentum Indicators (TA-Lib):
- rsi (RSI): overbought/oversold at 70/30 thresholds, divergence reversals.
- RSI6, RSI12: shorter/longer RSI periods via get_indicators()
- MOM1, MOM3, ROCR3, ROCR12: momentum and rate of change via get_indicators()
- WILLR, CCI12, CCI20: Williams %R and Commodity Channel Index via get_indicators()
- TRIX: triple exponential average via get_indicators()
- TSF10, TSF20: time series forecast via get_indicators()

Trend Strength (TA-Lib):
- ADX14, ADX20: average directional index via get_indicators()
- MFI14: money flow index (volume + momentum) via get_indicators()

Volatility Indicators (TA-Lib):
- boll (Bollinger Middle): 20 SMA, dynamic price benchmark.
- boll_ub (Bollinger Upper): 2 stdev above middle, overbought/breakout zones.
- boll_lb (Bollinger Lower): 2 stdev below middle, oversold signals.
- atr (ATR): volatility measure, stop-loss and position sizing.

Volume-Based Indicators:
- OBV: on-balance volume via get_indicators()
- vwma (VWMA): volume-weighted MA, trend+volume confirmation.

Candlestick Patterns:
- 61 candlestick patterns via TA-Lib (CDLDOJI, CDLHAMMER, CDLENGULFING, etc.)
- Automatically recognized; see pattern column names in OHLCV data

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names.

Before writing the final report, call get_verified_market_snapshot for this ticker and the current date, and treat it as the source of truth for any exact OHLCV, price-level, or indicator-value claim. If another tool's output conflicts with the verified snapshot, flag the discrepancy rather than inventing a reconciled number. Do not claim historical validation, support/resistance bounces, or exact percentage moves unless they are directly supported by tool output with concrete dates and prices.

Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
