# learnings.md - TA-Lib Integration

## 2026-05-27: Market analyst prompt updated

- Updated `tradingagents/agents/analysts/market_analyst.py` system_message indicator catalog
- Added candlestick patterns (61 via TA-Lib, single line), OBV, ADX, MFI
- Added RSI6/RSI12, MOM1/MOM3/ROCR3/ROCR12, WILLR, CCI12/CCI20, TRIX, TSF10/TSF20
- Grouped new "Trend Strength" section under TA-Lib header
- Appended "(TA-Lib)" to existing section headers (Moving Averages, MACD, Momentum, Volatility)
- Preserved all old indicators and the "Select indicators providing diverse..." instruction

## 2026-05-27: FeatureCalculator tests created

- Created `tests/test_feature_calculator.py` with 44 tests (25 pass, 19 skip without TA-Lib)
- 5 test classes: FeatureCalculatorTests, StockstatsToTalibMappingTests, FundamentalCacheTests, GetIndicatorsTaLibPathTests, FeatureCalculatorIntegrationTests
- Mocking patterns learned:
  - `_cached_or_fetch` lazy-imports `get_config` and `safe_ticker_component` inside the function body (not module-level), so must patch at their definition site: `tradingagents.dataflows.config.get_config` and `tradingagents.dataflows.utils.safe_ticker_component`
  - `_get_ta_feature` uses module-level `_ta_available` flag — can patch `tradingagents.agents.utils.technical_indicators_tools._ta_available`
  - Use `_make_ohlcv(days, seed)` helper for deterministic mock OHLCV data (seed=42 default)
  - Always clear `_ta_features_cache` in setUp/tearDown to prevent cross-test pollution
