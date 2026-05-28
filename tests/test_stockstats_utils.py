"""Tests for stockstats_utils.py — DataFrame cleaning, retry logic, financial filtering."""

from unittest.mock import MagicMock, patch
import time

import pandas as pd
import pytest
from yfinance.exceptions import YFRateLimitError

from tradingagents.dataflows.stockstats_utils import (
    yf_retry,
    _clean_dataframe,
    filter_financials_by_date,
)


# ---------------------------------------------------------------------------
# _clean_dataframe
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCleanDataframe:
    """Unit tests for _clean_dataframe — the guard clauses and normalization."""

    def test_empty_dataframe_returns_as_is(self):
        """Empty DataFrame should be returned without error."""
        df = pd.DataFrame()
        result = _clean_dataframe(df)
        assert result.empty

    def test_missing_date_column_returns_as_is(self):
        """DataFrame without 'Date' column should pass through untouched."""
        df = pd.DataFrame({"Open": [100.0], "Close": [101.0]})
        result = _clean_dataframe(df)
        assert "Date" not in result.columns
        assert result["Open"].iloc[0] == 100.0

    def test_clean_df_with_valid_date_column(self):
        """Valid DataFrame with string dates should be normalized."""
        df = pd.DataFrame({
            "Date": ["2024-01-15", "2024-01-16", "2024-01-17"],
            "Open": ["100.0", "101.0", "102.0"],
            "High": ["105.0", "106.0", "107.0"],
            "Low": ["95.0", "96.0", "97.0"],
            "Close": ["102.0", "103.0", "104.0"],
            "Volume": ["1000000", "1100000", "1200000"],
        })
        result = _clean_dataframe(df)
        assert len(result) == 3
        assert result["Close"].dtype == float
        assert result["Close"].iloc[1] == 103.0

    def test_nan_dates_dropped(self):
        """Rows with NaN dates should be dropped."""
        df = pd.DataFrame({
            "Date": ["2024-01-15", None, "2024-01-17"],
            "Open": [100.0, 101.0, 102.0],
            "Close": [102.0, 103.0, 104.0],
        })
        result = _clean_dataframe(df)
        assert len(result) == 2

    def test_missing_close_dropped(self):
        """Rows with NaN Close should be dropped."""
        df = pd.DataFrame({
            "Date": ["2024-01-15", "2024-01-16", "2024-01-17"],
            "Open": [100.0, 101.0, 102.0],
            "Close": [102.0, None, 104.0],
        })
        result = _clean_dataframe(df)
        assert len(result) == 2

    def test_partial_price_columns(self):
        """DataFrame with only some OHLCV columns should still work."""
        df = pd.DataFrame({
            "Date": ["2024-01-15", "2024-01-16"],
            "Close": [102.0, 103.0],
        })
        result = _clean_dataframe(df)
        assert len(result) == 2
        assert "Open" not in result.columns

    def test_non_numeric_prices_converted(self):
        """String prices should be converted to float."""
        df = pd.DataFrame({
            "Date": ["2024-01-15"],
            "Open": ["abc"],
            "Close": ["102.5"],
        })
        result = _clean_dataframe(df)
        assert len(result) == 1
        assert pd.isna(result["Open"].iloc[0])

    def test_already_datetime_worked(self):
        """Already-datetime Date column should be handled."""
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-15", "2024-01-16"]),
            "Open": [100.0, 101.0],
            "Close": [102.0, 103.0],
        })
        result = _clean_dataframe(df)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# yf_retry
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestYfRetry:
    """Unit tests for yf_retry — exponential backoff on rate limits."""

    def test_success_first_try(self):
        """Function succeeds immediately, no retries."""
        func = MagicMock(return_value="ok")
        result = yf_retry(func, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert func.call_count == 1

    def test_retries_on_rate_limit_then_succeeds(self):
        """Rate limit on first call, succeeds on second."""
        func = MagicMock(side_effect=[YFRateLimitError, "ok"])
        with patch.object(time, "sleep", return_value=None):
            result = yf_retry(func, max_retries=3, base_delay=0.001)
        assert result == "ok"
        assert func.call_count == 2

    def test_exhausts_retries_then_raises(self):
        """All attempts rate limited, raises YFRateLimitError."""
        func = MagicMock(side_effect=YFRateLimitError)
        with patch.object(time, "sleep", return_value=None):
            with pytest.raises(YFRateLimitError):
                yf_retry(func, max_retries=2, base_delay=0.001)
        assert func.call_count == 3  # initial + 2 retries

    def test_non_rate_limit_exception_propagates(self):
        """Non-rate-limit exceptions propagate immediately, no retries."""
        func = MagicMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            yf_retry(func, max_retries=3, base_delay=0.001)
        assert func.call_count == 1

    def test_exponential_backoff_doubles(self):
        """Delay should double each retry."""
        func = MagicMock(side_effect=[YFRateLimitError, YFRateLimitError, "ok"])
        with patch.object(time, "sleep") as mock_sleep:
            yf_retry(func, max_retries=3, base_delay=2.0)
        assert mock_sleep.call_args_list[0].args[0] == 2.0   # 2 * (2^0)
        assert mock_sleep.call_args_list[1].args[0] == 4.0   # 2 * (2^1)

    def test_zero_retries_allowed(self):
        """max_retries=0 means no retry, just one attempt."""
        func = MagicMock(side_effect=YFRateLimitError)
        with pytest.raises(YFRateLimitError):
            yf_retry(func, max_retries=0, base_delay=0.001)
        assert func.call_count == 1


# ---------------------------------------------------------------------------
# filter_financials_by_date
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFilterFinancialsByDate:
    """Unit tests for filter_financials_by_date — removes future fiscal periods."""

    def test_removes_future_columns(self):
        """Columns after curr_date are dropped."""
        df = pd.DataFrame(
            [[1, 2, 3], [4, 5, 6]],
            index=pd.Index(["Revenue", "Net Income"]),
            columns=pd.DatetimeIndex(["2023-12-31", "2024-12-31", "2025-12-31"]),
        )
        result = filter_financials_by_date(df, curr_date="2024-06-01")
        assert len(result.columns) == 1
        assert str(result.columns[0].date()) == "2023-12-31"

    def test_keeps_columns_on_or_before_date(self):
        """Columns exactly on curr_date are kept (not future)."""
        df = pd.DataFrame(
            [[1, 2]],
            index=pd.Index(["Revenue"]),
            columns=pd.DatetimeIndex(["2023-12-31", "2024-06-30"]),
        )
        result = filter_financials_by_date(df, curr_date="2024-06-30")
        assert len(result.columns) == 2

    def test_empty_dataframe_returns_empty(self):
        """Empty DataFrame passes through."""
        df = pd.DataFrame()
        result = filter_financials_by_date(df, curr_date="2024-06-01")
        assert result.empty

    def test_no_curr_date_returns_unchanged(self):
        """None/falsy curr_date returns data unchanged."""
        df = pd.DataFrame(
            [[1, 2]],
            index=pd.Index(["Revenue"]),
            columns=pd.DatetimeIndex(["2023-12-31", "2024-12-31"]),
        )
        result = filter_financials_by_date(df, curr_date=None)
        pd.testing.assert_frame_equal(result, df)

    def test_non_datetime_columns_preserved(self):
        """Columns that fail date parsing become NaT — dropped by the <= cutoff mask."""
        df = pd.DataFrame(
            [[1, 2, 3]],
            index=pd.Index(["Revenue"]),
            columns=["ttm", "2023-12-31", "2024-12-31"],
        )
        result = filter_financials_by_date(df, curr_date="2024-01-01")
        assert len(result.columns) >= 1


# ---------------------------------------------------------------------------
# StockstatsUtils.get_stock_stats — guard clause
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetStockStatsGuard:
    """Test the :no-data guard clause in StockstatsUtils.get_stock_stats."""

    def test_empty_ohlcv_returns_na_message(self):
        """When load_ohlcv returns empty data, return 'N/A: No data available'."""
        from tradingagents.dataflows.stockstats_utils import StockstatsUtils
        with patch(
            "tradingagents.dataflows.stockstats_utils.load_ohlcv",
            return_value=pd.DataFrame(),
        ):
            result = StockstatsUtils.get_stock_stats(
                symbol="FAKE",
                indicator="rsi",
                curr_date="2024-01-15",
            )
        assert result == "N/A: No data available"

    def test_missing_date_column_returns_na_message(self):
        """When load_ohlcv has no 'Date' column, return 'N/A: No data available'."""
        from tradingagents.dataflows.stockstats_utils import StockstatsUtils
        df = pd.DataFrame({
            "Open": [100.0, 101.0],
            "Close": [102.0, 103.0],
        })
        with patch(
            "tradingagents.dataflows.stockstats_utils.load_ohlcv",
            return_value=df,
        ):
            result = StockstatsUtils.get_stock_stats(
                symbol="FAKE",
                indicator="rsi",
                curr_date="2024-01-15",
            )
        assert result == "N/A: No data available"
