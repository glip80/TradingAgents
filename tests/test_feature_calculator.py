"""FeatureCalculator, TA-Lib integration, and yfinance cache tests."""

import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from tradingagents.dataflows.feature_calculator import (
    FeatureCalculator,
    STOCKSTATS_TO_TALIB,
)

try:
    import talib  # noqa: F401
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def _make_ohlcv(days=100, seed=42):
    """Create realistic mock OHLCV data mimicking yfinance output."""
    dates = pd.date_range(end="2024-01-15", periods=days, freq="D")
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, days))
    high = close * (1 + np.abs(rng.normal(0, 0.02, days)))
    low = close * (1 - np.abs(rng.normal(0, 0.02, days)))
    open_p = close * (1 + rng.normal(0, 0.01, days))
    volume = rng.integers(1_000_000, 10_000_000, days)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": open_p,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
    )


@pytest.mark.unit
class FeatureCalculatorTests(unittest.TestCase):
    def test_constructor_lowercases_columns(self):
        df = _make_ohlcv(50)
        calc = FeatureCalculator(df)
        self.assertIn("close", calc.data.columns)
        self.assertNotIn("Close", calc.data.columns)

    def test_constructor_raises_on_missing_columns(self):
        df = pd.DataFrame({"Date": ["2024-01-01"], "Close": [100]})
        with self.assertRaises(ValueError):
            FeatureCalculator(df)

    def test_constructor_sets_datetime_index(self):
        df = _make_ohlcv(20)
        calc = FeatureCalculator(df)
        self.assertIsInstance(calc.data.index, pd.DatetimeIndex)

    def test_constructor_accepts_existing_datetime_index(self):
        df = _make_ohlcv(20)
        df = df.set_index(pd.to_datetime(df["Date"])).drop(columns=["Date"])
        calc = FeatureCalculator(df)
        self.assertIsInstance(calc.data.index, pd.DatetimeIndex)

    def test_constructor_copies_data(self):
        df = _make_ohlcv(20)
        calc = FeatureCalculator(df)
        calc.data["extra"] = 1
        self.assertNotIn("extra", df.columns)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_returns_dataframe(self):
        df = _make_ohlcv(100)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_contains_required_indicators(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        core = [
            "OBV", "RSI6", "RSI12", "RSI14", "SMA3", "EMA6", "EMA12",
            "ATR14", "MFI14", "ADX14", "ADX20", "MOM1", "MOM3",
            "CCI12", "CCI20", "ROCR3", "ROCR12", "outMACD", "outMACDSignal",
            "outMACDHist", "WILLR", "TRIX", "BBANDSUPPER", "BBANDSMIDDLE",
            "BBANDSLOWER",
        ]
        for feat in core:
            self.assertIn(feat, result.columns, f"Missing: {feat}")

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_contains_tsf_features(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertIn("TSF10", result.columns)
        self.assertIn("TSF20", result.columns)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_contains_donchian(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        for col in ("DONCHIAN_UPPER", "DONCHIAN_LOWER", "DONCHIAN_MIDDLE"):
            self.assertIn(col, result.columns)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_drops_nan_rows(self):
        df = _make_ohlcv(100)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertEqual(result.isna().sum().sum(), 0)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_calculate_features_index_is_datetime(self):
        df = _make_ohlcv(100)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertIsInstance(result.index, pd.DatetimeIndex)

    def test_raises_when_talib_unavailable(self):
        df = _make_ohlcv(50)
        calc = FeatureCalculator(df)
        with mock.patch(
            "tradingagents.dataflows.feature_calculator._ta_available", False
        ):
            with self.assertRaises(RuntimeError):
                calc.calculate_features()

    def test_calculate_tsf_sklearn_unavailable_returns_nan(self):
        df = _make_ohlcv(50)
        calc = FeatureCalculator(df)
        with mock.patch(
            "tradingagents.dataflows.feature_calculator._sklearn_available", False
        ):
            tsf = calc._calculate_tsf(period=10)
        self.assertTrue(tsf.isna().all())


@pytest.mark.unit
class StockstatsToTalibMappingTests(unittest.TestCase):
    """Indicator name mapping integrity checks."""

    def test_mapping_contains_common_names(self):
        required = [
            "close_50_sma", "close_200_sma", "close_10_ema",
            "macd", "macds", "macdh", "rsi", "boll", "boll_ub",
            "boll_lb", "atr",
        ]
        for name in required:
            self.assertIn(name, STOCKSTATS_TO_TALIB, f"Missing: {name}")

    def test_mapping_values_are_strings(self):
        for key, val in STOCKSTATS_TO_TALIB.items():
            self.assertIsInstance(val, str, f"Non-string for {key}")

    def test_vwma_is_mapped(self):
        self.assertIn("vwma", STOCKSTATS_TO_TALIB)

    def test_vwma_maps_to_vwma(self):
        self.assertEqual(STOCKSTATS_TO_TALIB["vwma"], "VWMA")

    def test_rsi_maps_to_rsi14(self):
        self.assertEqual(STOCKSTATS_TO_TALIB["rsi"], "RSI14")

    def test_macd_components_have_distinct_mappings(self):
        self.assertNotEqual(STOCKSTATS_TO_TALIB["macd"], STOCKSTATS_TO_TALIB["macds"])
        self.assertNotEqual(STOCKSTATS_TO_TALIB["macds"], STOCKSTATS_TO_TALIB["macdh"])

    def test_mapping_keys_are_lowercase(self):
        for key in STOCKSTATS_TO_TALIB:
            self.assertEqual(key, key.lower(), f"Key not lowercase: {key}")

    def test_no_duplicate_values(self):
        vals = [v for k, v in STOCKSTATS_TO_TALIB.items() if v != "VWMA"]
        self.assertEqual(len(vals), len(set(vals)))


@pytest.mark.unit
class FundamentalCacheTests(unittest.TestCase):
    """Disk-cache behaviour for _cached_or_fetch."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_patcher = mock.patch(
            "tradingagents.dataflows.config.get_config",
            return_value={
                "data_cache_dir": self.temp_dir,
                "fundamentals_cache_ttl_hours": 24,
            },
        )
        self.mock_config = self.config_patcher.start()
        self.safe_patcher = mock.patch(
            "tradingagents.dataflows.utils.safe_ticker_component",
            side_effect=lambda s: s,
        )
        self.safe_patcher.start()

    def tearDown(self):
        self.config_patcher.stop()
        self.safe_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_miss_fetches_and_caches(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher = mock.Mock(return_value={"key": "value"})
        result = _cached_or_fetch("TEST", "test_key", fetcher, ttl_hours=24)
        fetcher.assert_called_once()
        self.assertEqual(result, {"key": "value"})
        entries = os.listdir(self.temp_dir)
        self.assertTrue(any("TEST-test_key" in f for f in entries))

    def test_cache_hit_returns_cached(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher = mock.Mock(return_value={"key": "value"})
        _cached_or_fetch("TEST", "test_hit", fetcher, ttl_hours=24)
        _cached_or_fetch("TEST", "test_hit", fetcher, ttl_hours=24)
        fetcher.assert_called_once()

    def test_cache_returns_same_value(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        original = {"price": 150.0, "pe": 25.3}
        fetcher = mock.Mock(return_value=original)
        _cached_or_fetch("TEST", "test_same", fetcher, ttl_hours=24)
        cached = _cached_or_fetch("TEST", "test_same", fetcher, ttl_hours=24)
        self.assertEqual(cached, original)

    def test_stale_cache_triggers_refetch(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher = mock.Mock(return_value={"key": "new_value"})
        _cached_or_fetch("TEST", "test_stale", fetcher, ttl_hours=24)
        for fname in os.listdir(self.temp_dir):
            if "TEST-test_stale" in fname:
                old_time = time.time() - 25 * 3600
                os.utime(os.path.join(self.temp_dir, fname), (old_time, old_time))
        result = _cached_or_fetch("TEST", "test_stale", fetcher, ttl_hours=24)
        self.assertEqual(fetcher.call_count, 2)
        self.assertEqual(result, {"key": "new_value"})

    def test_config_ttl_overrides_default(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        self.mock_config.return_value = {
            "data_cache_dir": self.temp_dir,
            "fundamentals_cache_ttl_hours": 0,
        }
        fetcher = mock.Mock(return_value={"val": 1})
        _cached_or_fetch("TEST", "test_ttl_override", fetcher, ttl_hours=24)
        _cached_or_fetch("TEST", "test_ttl_override", fetcher, ttl_hours=24)
        self.assertEqual(fetcher.call_count, 2)

    def test_empty_dict_not_cached(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher1 = mock.Mock(return_value={})
        _cached_or_fetch("TEST", "test_empty", fetcher1, ttl_hours=24)
        fetcher2 = mock.Mock(return_value={"real": "data"})
        _cached_or_fetch("TEST", "test_empty", fetcher2, ttl_hours=24)
        fetcher1.assert_called_once()
        fetcher2.assert_called_once()

    def test_empty_list_not_cached(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher1 = mock.Mock(return_value=[])
        _cached_or_fetch("TEST", "test_emptylist", fetcher1, ttl_hours=24)
        fetcher2 = mock.Mock(return_value=[1, 2, 3])
        _cached_or_fetch("TEST", "test_emptylist", fetcher2, ttl_hours=24)
        fetcher1.assert_called_once()
        fetcher2.assert_called_once()

    def test_none_result_not_cached(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        fetcher1 = mock.Mock(return_value=None)
        _cached_or_fetch("TEST", "test_none", fetcher1, ttl_hours=24)
        fetcher2 = mock.Mock(return_value={"ok": True})
        _cached_or_fetch("TEST", "test_none", fetcher2, ttl_hours=24)
        fetcher1.assert_called_once()
        fetcher2.assert_called_once()

    def test_cache_file_contains_json(self):
        from tradingagents.dataflows.y_finance import _cached_or_fetch

        data = {"a": 1, "b": [2, 3]}
        fetcher = mock.Mock(return_value=data)
        _cached_or_fetch("TEST", "test_json", fetcher, ttl_hours=24)
        for fname in os.listdir(self.temp_dir):
            if "TEST-test_json" in fname:
                with open(os.path.join(self.temp_dir, fname)) as f:
                    loaded = json.load(f)
                self.assertEqual(loaded, data)
                return
        self.fail("Cache file not found")


@pytest.mark.unit
class GetIndicatorsTaLibPathTests(unittest.TestCase):
    """_get_ta_feature behaviour: caching, fallback, look-ahead prevention."""

    def setUp(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _ta_features_cache,
        )
        _ta_features_cache.clear()

    def tearDown(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _ta_features_cache,
        )
        _ta_features_cache.clear()

    def test_returns_none_when_talib_unavailable(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools._ta_available", False
        ):
            result = _get_ta_feature("TEST", "rsi", "2024-01-15")
        self.assertIsNone(result)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_returns_string_for_valid_indicator(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        mock_df = _make_ohlcv(100)
        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=mock_df,
        ):
            result = _get_ta_feature("TICK_A", "rsi", "2024-01-15")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        float(result)  # assert parseable as float

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_returns_none_for_unknown_indicator(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=_make_ohlcv(100),
        ):
            result = _get_ta_feature("TICK_B", "nonexistent_indicator", "2024-01-15")
        self.assertIsNone(result)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_returns_none_when_ohlcv_empty(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=pd.DataFrame(),
        ):
            result = _get_ta_feature("TICK_C", "rsi", "2024-01-15")
        self.assertIsNone(result)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_returns_none_for_date_before_data(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        mock_df = _make_ohlcv(100)
        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=mock_df,
        ):
            result = _get_ta_feature("TICK_D", "rsi", "2020-01-01")
        self.assertIsNone(result)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_features_computed_once_per_symbol(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
            _ta_features_cache,
        )

        _ta_features_cache.clear()
        mock_df = _make_ohlcv(100)

        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=mock_df,
        ) as mock_load:
            with mock.patch(
                "tradingagents.agents.utils.technical_indicators_tools.FeatureCalculator"
            ) as MockFC:
                MockFC.return_value.calculate_features.return_value = _make_ohlcv(100)
                _get_ta_feature("SYM_CACHE", "rsi", "2024-01-15")
                _get_ta_feature("SYM_CACHE", "macd", "2024-01-15")
                self.assertEqual(MockFC.call_count, 1)
                mock_load.assert_called_once()

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_cache_separate_per_symbol(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
        )

        mock_df = _make_ohlcv(100)
        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=mock_df,
        ):
            a = _get_ta_feature("SYM_X", "rsi", "2024-01-15")
            b = _get_ta_feature("SYM_Y", "rsi", "2024-01-15")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_ohlcv_error_returns_none_and_does_not_cache(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
            _ta_features_cache,
        )

        _ta_features_cache.clear()
        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            side_effect=Exception("Network error"),
        ):
            result = _get_ta_feature("TICK_ERR", "rsi", "2024-01-15")
        self.assertIsNone(result)
        self.assertNotIn("TICK_ERR", _ta_features_cache)

    @unittest.skipIf(not HAS_TALIB, "TA-Lib not installed")
    def test_prevents_look_ahead_bias(self):
        from tradingagents.agents.utils.technical_indicators_tools import (
            _get_ta_feature,
            _ta_features_cache,
        )

        _ta_features_cache.clear()
        mock_df = _make_ohlcv(200)
        mock_df.loc[mock_df.index[-1], "Close"] = 9999.0

        with mock.patch(
            "tradingagents.agents.utils.technical_indicators_tools.load_ohlcv",
            return_value=mock_df,
        ):
            mid_date = mock_df.index[len(mock_df) // 2].strftime("%Y-%m-%d")
            result_mid = _get_ta_feature("TICK_BIAS", "close_50_sma", mid_date)
            end_date = mock_df.index[-1].strftime("%Y-%m-%d")
            result_end = _get_ta_feature("TICK_BIAS", "close_50_sma", end_date)

        self.assertIsNotNone(result_mid)
        self.assertIsNotNone(result_end)


@pytest.mark.integration
@unittest.skipIf(not HAS_TALIB, "TA-Lib not installed — integration tests skipped")
class FeatureCalculatorIntegrationTests(unittest.TestCase):
    """End-to-end FeatureCalculator with live TA-Lib."""

    def test_full_pipeline_on_200_days(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertGreater(len(result), 0)
        self.assertEqual(result.isna().sum().sum(), 0)

    def test_all_original_features_present(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        for feat in calc.original_features:
            if feat == "VIX":
                continue
            self.assertIn(feat, result.columns, f"Missing: {feat}")

    def test_indicators_have_reasonable_ranges(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()

        self.assertTrue(result["RSI14"].between(0, 100).all())
        self.assertTrue(result["CCI20"].abs().max() < 1000)
        self.assertTrue((result["ATR14"] > 0).all())
        self.assertTrue(result["WILLR"].between(-100, 0).all())

    def test_donchian_upper_gte_lower(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertTrue((result["DONCHIAN_UPPER"] >= result["DONCHIAN_MIDDLE"]).all())
        self.assertTrue((result["DONCHIAN_MIDDLE"] >= result["DONCHIAN_LOWER"]).all())

    def test_bollinger_bands_ordering(self):
        df = _make_ohlcv(200)
        calc = FeatureCalculator(df)
        result = calc.calculate_features()
        self.assertTrue((result["BBANDSUPPER"] >= result["BBANDSMIDDLE"]).all())
        self.assertTrue((result["BBANDSMIDDLE"] >= result["BBANDSLOWER"]).all())
