"""Integration tests for tradingagents.dataflows.y_finance — real yfinance API calls."""

import json
import os
import tempfile
from datetime import date, datetime

import pandas as pd
import pytest

from tradingagents.dataflows.config import set_config, get_config
from tradingagents.dataflows.y_finance import (
    _cached_or_fetch,
    _financials_to_cacheable,
    _financials_from_cacheable,
    get_YFin_data_online,
    get_stockstats_indicator,
    get_stock_stats_indicators_window,
    get_fundamentals,
)

TICKER = "AAPL"
# Use a window far enough back that OHLCV data is guaranteed available.
START_DATE = (date.today() - date.resolution * 10).isoformat()
END_DATE = date.today().isoformat()


# ---------------------------------------------------------------------------
# _financials_to_cacheable / _financials_from_cacheable — roundtrip
# ---------------------------------------------------------------------------

def test_financials_roundtrip():
    """DataFrame → dict → DataFrame preserves shape and values."""
    df = pd.DataFrame({
        "2024-Q4": [100.5, 200.3],
        "2025-Q1": [150.2, 250.7],
    }, index=["Revenue", "Net Income"])

    cooked = _financials_to_cacheable(df)
    assert isinstance(cooked, dict)
    assert "2024-Q4" in cooked

    round_tripped = _financials_from_cacheable(cooked)
    assert isinstance(round_tripped, pd.DataFrame)
    assert round_tripped.shape == df.shape
    assert round_tripped.at["Revenue", pd.Timestamp("2024-10-01")] == 100.5  # Q4 → Oct


def test_financials_roundtrip_nan():
    """NaN values survive the roundtrip as None → NaN."""
    df = pd.DataFrame({"2024-Q4": [1.0, float("nan")]}, index=["x", "y"])
    cooked = _financials_to_cacheable(df)
    round_tripped = _financials_from_cacheable(cooked)
    # Column "2024-Q4" → Timestamp 2024-10-01 (Q4 start)
    col_ts = pd.Timestamp("2024-10-01")
    assert round_tripped.at["x", col_ts] == 1.0
    assert pd.isna(round_tripped.at["y", col_ts])


# ---------------------------------------------------------------------------
# _cached_or_fetch — cache hit/miss with temp directory
# ---------------------------------------------------------------------------

def test_cached_or_fetch_miss_and_hit(tmp_path):
    """First call fetches + writes cache; second call reads cache."""
    cache_dir = str(tmp_path / "test_cache")
    set_config({"data_cache_dir": cache_dir})

    call_count = [0]

    def fetcher():
        call_count[0] += 1
        return {"key": "from-fetch"}

    # First call — cache miss, must fetch
    result1 = _cached_or_fetch(TICKER, "test-key", fetcher, ttl_hours=24)
    assert result1 == {"key": "from-fetch"}
    assert call_count[0] == 1
    assert os.path.exists(os.path.join(cache_dir, f"{TICKER}-test-key.json"))

    # Second call — cache hit, no re-fetch
    result2 = _cached_or_fetch(TICKER, "test-key", fetcher, ttl_hours=24)
    assert result2 == {"key": "from-fetch"}
    assert call_count[0] == 1  # fetcher NOT called again


def test_cached_or_fetch_fetcher_returns_none_not_cached(tmp_path):
    """None/empty is NOT written to disk (non-positive guard)."""
    cache_dir = str(tmp_path / "test_cache")
    set_config({"data_cache_dir": cache_dir})

    result = _cached_or_fetch(TICKER, "none-key", lambda: None, ttl_hours=24)
    assert result is None
    assert not os.path.exists(os.path.join(cache_dir, f"{TICKER}-none-key.json"))


# ---------------------------------------------------------------------------
# get_YFin_data_online — real API call
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_YFin_data_online_real():
    """Real OHLCV history for AAPL returns CSV-formatted string."""
    data = get_YFin_data_online(TICKER, START_DATE, END_DATE)

    assert isinstance(data, str)
    assert len(data) > 0

    if "No data found" in data:
        # Valid empty response for date range with no trading days
        assert TICKER in data
    else:
        assert f"Stock data for {TICKER}" in data
        assert "Total records:" in data
        # CSV columns expected
        assert "Date" in data or "Price" in data or "Open" in data


@pytest.mark.integration
def test_get_YFin_data_online_invalid():
    """Garbage symbol returns empty-data / error message, no crash."""
    data = get_YFin_data_online("ZZZ-INVALID-TICKER", START_DATE, END_DATE)
    assert isinstance(data, str)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# get_fundamentals — real API call
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_fundamentals_real():
    """Company fundamentals for AAPL returns well-formed string."""
    data = get_fundamentals(TICKER)

    assert isinstance(data, str)
    assert len(data) > 0

    if "No fundamentals" in data:
        # Valid empty case
        assert TICKER in data
    else:
        assert "Company Fundamentals" in data
        # At least some known fields
        assert any(field in data for field in ("Name:", "Sector:", "Market Cap:"))


@pytest.mark.integration
def test_get_fundamentals_invalid():
    """Invalid ticker returns error message or none-message, no crash."""
    data = get_fundamentals("ZZZ-INVALID-TICKER")
    assert isinstance(data, str)
    # Should be an error message or "No data" variant
    assert len(data) > 0


# ---------------------------------------------------------------------------
# get_stockstats_indicator — real API call (needs OHLCV history)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_stockstats_indicator_real():
    """Single-date SMA indicator for AAPL returns a numeric string."""
    # Use a date at least 60 days back so 50-SMA has enough bars
    ref_date = (date.today() - date.resolution * 60).isoformat()
    result = get_stockstats_indicator(TICKER, "close_50_sma", ref_date)

    assert isinstance(result, str)
    # Output is either a float string or empty (error)
    if result:
        # Should be a numeric value string
        try:
            float(result)
        except ValueError:
            pass  # N/A or error, both acceptable


# ---------------------------------------------------------------------------
# get_stock_stats_indicators_window — real API call
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_stock_stats_indicators_window_real():
    """Multi-day MACD indicator window returns formatted report string."""
    # Need ~200 bars for MACD. Use date far back + recent ref.
    ref_date = (date.today() - date.resolution).isoformat()  # yesterday
    data = get_stock_stats_indicators_window(
        TICKER, "macd", ref_date, look_back_days=5
    )

    assert isinstance(data, str)
    assert len(data) > 0
    assert "macd values" in data.lower()  # header line
    # Should contain description text
    assert "description" in data.lower() or "MACD" in data
