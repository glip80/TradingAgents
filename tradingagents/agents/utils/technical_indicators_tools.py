from langchain_core.tools import tool
from typing import Annotated

import pandas as pd

from tradingagents.dataflows.feature_calculator import (
    FeatureCalculator,
    STOCKSTATS_TO_TALIB,
    _ta_available,
)
from tradingagents.dataflows.stockstats_utils import load_ohlcv
from tradingagents.dataflows.interface import route_to_vendor

# Module-level cache: symbol -> computed features DataFrame.
# Features are computed once per symbol and reused across calls.
_ta_features_cache: dict[str, pd.DataFrame] = {}


def _get_ta_feature(symbol: str, indicator: str, curr_date: str) -> str | None:
    """Try to get indicator value from TA-Lib FeatureCalculator.

    Returns the value as a string if successful, or None if TA-Lib is
    unavailable, the indicator is not mappable, or any error occurs.
    """
    if not _ta_available:
        return None

    ta_col = STOCKSTATS_TO_TALIB.get(indicator.lower())
    if ta_col is None:
        return None

    if symbol not in _ta_features_cache:
        try:
            data = load_ohlcv(symbol, curr_date)
            if data.empty:
                return None
            calculator = FeatureCalculator(data)
            features = calculator.calculate_features()
            _ta_features_cache[symbol] = features
        except Exception:
            return None

    df = _ta_features_cache[symbol]
    curr_date_dt = pd.to_datetime(curr_date)

    # Filter rows up to curr_date to prevent look-ahead bias
    matching = df.loc[df.index <= curr_date_dt]
    if matching.empty:
        return None

    latest = matching.iloc[-1]
    if ta_col not in latest.index or pd.isna(latest[ta_col]):
        return None

    return str(latest[ta_col])


@tool
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Retrieve a single technical indicator for a given ticker symbol.
    Uses the configured technical_indicators vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        indicator (str): A single technical indicator name, e.g. 'rsi', 'macd'. Call this tool once per indicator.
        curr_date (str): The current trading date you are trading on, YYYY-mm-dd
        look_back_days (int): How many days to look back, default is 30
    Returns:
        str: A formatted dataframe containing the technical indicators for the specified ticker symbol and indicator.
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    indicators = [i.strip().lower() for i in indicator.split(",") if i.strip()]
    results = []
    for ind in indicators:
        # Try TA-Lib fast path first
        ta_val = _get_ta_feature(symbol, ind, curr_date)
        if ta_val is not None:
            results.append(ta_val)
        else:
            # Fallback to original stockstats vendor routing
            try:
                results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
            except ValueError as e:
                results.append(str(e))
    return "\n\n".join(results)
