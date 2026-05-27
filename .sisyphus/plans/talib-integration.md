# TA-Lib Integration + yfinance Caching

## TL;DR

> **Quick Summary**: Replace stockstats-based `get_indicators` with TA-Lib `FeatureCalculator` (90+ features, C-backed, one-pass). Add disk caching for yfinance fundamental data (info, balance sheet, cashflow, income statement). Result: richer indicators, 10x faster computation, no redundant API calls.

> **Deliverables**:
> - `tradingagents/dataflows/feature_calculator.py` — adapted from the standalone version
> - `tradingagents/agents/utils/technical_indicators_tools.py` — replace stockstats with TA-Lib
> - `tradingagents/dataflows/y_finance.py` — add caching to fundamental functions
> - Updated market analyst prompt — richer indicator catalog
> - Tests for feature calculator + cache behavior

> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4

---

## Context

### Original Request
Use `feature_calculator.py` (TA-Lib) as an improvement over current stockstats-based indicators. Add caching to yfinance fundamental data.

### Current State
- `get_indicators(ticker, indicator_name)` — queries stockstats per-indicator, per-date. Slow. 12 indicators max.
- `get_fundamentals/balance_sheet/cashflow/income_statement` — live yfinance API call every time. No caching.
- `load_ohlcv()` — already cached to `~/.tradingagents/cache/` (this is fine).

### Target State
- TA-Lib `FeatureCalculator` computes ALL indicators (29 + 61 candlestick patterns) in one pass from OHLCV
- Indicator results stored in graph state as CSV/DataFrame — `get_indicators` reads from pre-computed data
- Fundament data cached per-ticker to `~/.tradingagents/cache/{symbol}-info.json`, etc.
- Market analyst gets 90 indicator options instead of 12

### Performance Impact
| Metric | Before | After |
|--------|--------|-------|
| Indicators computed | 12 (per call) | 90 (one pass) |
| Indicator latency | ~2s per indicator | ~0.1s total (TA-Lib C pass) |
| Fundamental API calls | Every run | Once per 24h (cached) |
| Market analyst prompt tokens | 757 | ~500 (richer but trimmed) |
| Candlestick patterns | None | 61 patterns available |

---

## Work Objectives

### Core Objective
Integrate TA-Lib FeatureCalculator into the TradingAgents data pipeline and add disk caching for yfinance fundamental data.

### Concrete Deliverables
- Adapted: `tradingagents/dataflows/feature_calculator.py` — copy from standalone, adjust imports to tradingagents
- Modified: `tradingagents/agents/utils/technical_indicators_tools.py` — `get_indicators` reads from pre-computed features
- Modified: `tradingagents/dataflows/y_finance.py` — add caching decorator to fundamental functions
- Modified: `tradingagents/agents/analysts/market_analyst.py` — updated indicator list in system_message
- New: `tests/test_feature_calculator.py`

### Definition of Done
- [ ] `get_indicators` returns TA-Lib computed values instead of stockstats
- [ ] 90 features (29 technical + 61 patterns) available to market analyst
- [ ] Fundamental data cached to disk, refreshed every 24h
- [ ] OHLCV loaded once, features calculated once — no redundant computation
- [ ] All existing tests pass
- [ ] New feature calculator tests pass

### Must Have
- TA-Lib installed as dependency (added to pyproject.toml if not already)
- FeatureCalculator integrated into the `load_ohlcv → calculate features → return` pipeline
- Cache invalidation: fundamental data cache TTL = 24 hours (configurable via config)
- Backward compat: old indicator names (close_50_sma, rsi, macd, etc.) still work via mapping

### Must NOT Have
- Must NOT remove stockstats — keep as fallback if TA-Lib unavailable
- Must NOT require TA-Lib to be installed for basic functionality (graceful degradation)
- Must NOT change the tool interface — `get_indicators(symbol, indicator)` keeps same signature
- Must NOT break the existing indicator name API — old names must map to new computation

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after
- **Framework**: pytest

### QA Policy
Agent-executed QA scenarios per task.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: Add TA-Lib dependency + adapt FeatureCalculator [quick]
└── Task 2: Add yfinance caching decorator [quick]

Wave 2 (After Wave 1 — integration):
├── Task 3: Replace get_indicators with TA-Lib [deep]
├── Task 4: Update market analyst prompt [quick]
└── Task 5: Tests for FeatureCalculator + cache [deep]

Wave FINAL:
├── Task F1: Full test suite [unspecified-high]
└── Task F2: Performance benchmark [unspecified-high]
```

**Critical Path**: Task 1 → Task 3 → Task 4 → F1-F2

---

## TODOs

- [x] 1. **Add TA-Lib dependency + adapt FeatureCalculator**

  **What to do**:
  - Add `ta-lib` to `pyproject.toml` dependencies
  - Copy `FeatureCalculator` class from the standalone file to `tradingagents/dataflows/feature_calculator.py`
  - Adapt imports: replace `from trend_predictor.utils import setup_logging` → `from tradingagents.logging import get_logger`
  - Add graceful fallback: `_ta_available = True` try/except on `import talib`
  - Columns: ensure lowercase mapping works with yfinance data (already handles this)
  - Remove VIX/candlestick self-call from `calculate_features` — keep them as configurable options (the standalone has them commented out)
  - Add indicator name mapping for backward compat:
    ```python
    STOCKSTATS_TO_TALIB = {
        "close_50_sma": "SMA50",  # TA-Lib SMA with period 50
        "close_200_sma": "SMA200",
        "close_10_ema": "EMA10",
        "macd": "outMACD",
        "macds": "outMACDSignal",
        "macdh": "outMACDHist",
        "rsi": "RSI14",  # RSI14 = new feature we add
        "boll": "BBANDSMIDDLE",
        "boll_ub": "BBANDSUPPER",
        "boll_lb": "BBANDSLOWER",
        "atr": "ATR14",
        "vwma": "VWMA",  # needs custom calc or fallback to stockstats
    }
    ```

  **Must NOT do**:
  - Do NOT copy the `__main__` block — only the class
  - Do NOT hardcode `trend_predictor` path — use tradingagents logging

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Can run in parallel with Task 2
  **Blocked By**: None

  **References**:
  - `tradingagents/dataflows/stockstats_utils.py` — current indicator pipeline (what we're replacing)
  - `pyproject.toml:12-34` — dependency list (add ta-lib here)
  - Standalone `feature_calculator.py` — source to adapt

  **QA Scenarios**:
  ```
  Scenario: FeatureCalculator loads and imports cleanly
    Tool: Bash (python)
    Steps:
      1. pip install ta-lib (or verify already present)
      2. python -c "from tradingagents.dataflows.feature_calculator import FeatureCalculator; print('OK')"
    Expected Result: OK, no import errors
    Evidence: .sisyphus/evidence/task-1-import.txt

  Scenario: Graceful fallback when TA-Lib missing
    Tool: Bash (python, mock)
    Steps:
      1. Patch import to simulate missing talib
      2. Verify FeatureCalculator._ta_available is False
      3. Verify no crash on import
    Expected Result: Graceful degradation, no crash
    Evidence: .sisyphus/evidence/task-1-fallback.txt
  ```

  **Commit**: YES
  - Message: `feat(data): add TA-Lib FeatureCalculator with 90+ indicators`
  - Files: `tradingagents/dataflows/feature_calculator.py`, `pyproject.toml`

- [x] 2. **Add yfinance fundamental data caching**

  **What to do**:
  - Add caching helper function in `tradingagents/dataflows/y_finance.py`:
    ```python
    def _cached_or_fetch(symbol, cache_key, fetcher, ttl_hours=24):
        cache_dir = get_config()["data_cache_dir"]
        cache_file = os.path.join(cache_dir, f"{symbol}-{cache_key}.json")
        if os.path.exists(cache_file):
            age = time.time() - os.path.getmtime(cache_file)
            if age < ttl_hours * 3600:
                with open(cache_file) as f:
                    return json.load(f)
        data = yf_retry(fetcher)
        with open(cache_file, 'w') as f:
            json.dump(data, f, default=str)
        return data
    ```
  - Apply to: `get_fundamentals` (caches `ticker_obj.info` dict), `get_balance_sheet` (caches DataFrame), `get_cashflow`, `get_income_statement`
  - For DataFrame returns: serialize to JSON (use `.to_dict()`)
  - TTL: 24 hours default, configurable via `config["fundamentals_cache_ttl_hours"]`
  - Safe symbol: use `safe_ticker_component(symbol)` for cache filename

  **Must NOT do**:
  - Do NOT cache OHLCV (already cached by `load_ohlcv`)
  - Do NOT cache empty/error results — only cache on success
  - Do NOT change the return format of any function

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Can run in parallel with Task 1
  **Blocked By**: None

  **References**:
  - `tradingagents/dataflows/stockstats_utils.py:68-98` — existing OHLCV cache pattern
  - `tradingagents/dataflows/y_finance.py:248-297` — `get_fundamentals`
  - `tradingagents/dataflows/y_finance.py:316-340` — `get_balance_sheet`
  - `tradingagents/dataflows/y_finance.py:348-372` — `get_cashflow`
  - `tradingagents/dataflows/y_finance.py:380-404` — `get_income_statement`
  - `tradingagents/dataflows/config.py` — `get_config()["data_cache_dir"]`

  **QA Scenarios**:
  ```
  Scenario: First call fetches from API, second call reads cache
    Tool: Bash (python REPL)
    Preconditions: Mock yfinance to return known data
    Steps:
      1. Call get_fundamentals("AAPL") → verify API called
      2. Call get_fundamentals("AAPL") again → verify cache hit (no API call)
      3. Check cache file exists in data_cache_dir
    Expected Result: Second call uses cache, no API call
    Evidence: .sisyphus/evidence/task-2-cache-hit.txt

  Scenario: Stale cache (24h+) triggers refresh
    Tool: Bash (python REPL)
    Steps:
      1. Create cache file with old timestamp
      2. Call get_fundamentals → verify API called (cache expired)
    Expected Result: Cache refresh triggered
    Evidence: .sisyphus/evidence/task-2-cache-expire.txt
  ```

  **Commit**: YES
  - Message: `perf(data): add 24h disk cache for yfinance fundamental data`
  - Files: `tradingagents/dataflows/y_finance.py`, `tradingagents/default_config.py`

- [x] 3. **Replace get_indicators with TA-Lib FeatureCalculator**

  **What to do**:
  - In `tradingagents/agents/utils/technical_indicators_tools.py`:
  - After `load_ohlcv()` → run `FeatureCalculator(data).calculate_features()` if TA-Lib available
  - Store computed features DataFrame in a module-level cache (per symbol): `_ta_features_cache: dict[str, pd.DataFrame] = {}`
  - `get_indicators(symbol, indicator, curr_date)` → maps indicator name via `STOCKSTATS_TO_TALIB`, looks up value in cached DataFrame
  - Fallback: if TA-Lib unavailable or indicator not mapped, use existing stockstats path
  - Return format unchanged (CSV-like string)
  - Add all 29 TA-Lib indicators as available in the mapping:
    - OBV, RSI6, RSI12, RSI14, SMA3, SMA50, SMA200, EMA6, EMA12, EMA10, ATR14, MFI14, ADX14, ADX20, MOM1, MOM3, CCI12, CCI20, ROCR3, ROCR12, outMACD, outMACDSignal, outMACDHist, WILLR, TSF10, TSF20, TRIX, BBANDSUPPER, BBANDSMIDDLE, BBANDSLOWER, DONCHIAN_*, VIX

  **Must NOT do**:
  - Do NOT regenerate features for every `get_indicators` call — compute once per symbol
  - Do NOT remove the stockstats fallback path

  **Recommended Agent Profile**: `deep`
  **Parallelization**: After Tasks 1, 2
  **Blocked By**: Task 1

  **References**:
  - `tradingagents/agents/utils/technical_indicators_tools.py` — current `get_indicators`
  - `tradingagents/dataflows/stockstats_utils.py:122-148` — `StockstatsUtils.get_stock_stats` (to replace)
  - `tradingagents/dataflows/feature_calculator.py` — new FeatureCalculator (from Task 1)

  **QA Scenarios**:
  ```
  Scenario: get_indicators returns TA-Lib computed RSI
    Tool: Bash (python REPL)
    Steps:
      1. Load OHLCV for SPY
      2. Call get_indicators("SPY", "rsi", "2024-01-15")
      3. Verify result is numeric string (not N/A, not error)
    Expected Result: Numeric RSI value
    Evidence: .sisyphus/evidence/task-3-talib-rsi.txt

  Scenario: Unknown indicator falls back to stockstats
    Tool: Bash (python REPL)
    Steps:
      1. Call get_indicators("SPY", "nonexistent_indicator", "2024-01-15")
      2. Verify fallback to stockstats or returns error message
    Expected Result: Graceful handling
    Evidence: .sisyphus/evidence/task-3-fallback.txt

  Scenario: Features computed once, reused across calls
    Tool: Bash (python REPL)
    Steps:
      1. Call get_indicators for 5 different indicators on same symbol
      2. Verify FeatureCalculator.calculate_features called only once
    Expected Result: Single computation, multiple lookups
    Evidence: .sisyphus/evidence/task-3-once.txt
  ```

  **Commit**: YES
  - Message: `feat(indicators): replace stockstats with TA-Lib FeatureCalculator (90+ features)`
  - Files: `tradingagents/agents/utils/technical_indicators_tools.py`

- [x] 4. **Update market analyst prompt for richer indicator set**

  **What to do**:
  - In `tradingagents/agents/analysts/market_analyst.py`:
  - Update the indicator catalog section of `system_message` to include TA-Lib indicators
  - Add new indicator groups:
    - Candlestick patterns (mention they're available via pattern recognition)
    - Volume indicators (OBV, MFI)
    - Trend strength (ADX)
  - Keep trimmed format from quick-wins plan (1-line per indicator)
  - Mark which indicators require `get_indicators(indicator_name)` vs which are always present

  **Must NOT do**:
  - Do NOT list all 61 candlestick patterns by name — group them as "Candlestick pattern recognition (61 patterns via TA-Lib)"
  - Do NOT remove the "Select indicators that provide diverse..." instruction

  **Recommended Agent Profile**: `quick`
  **Parallelization**: After Task 3
  **Blocked By**: Task 3

  **QA Scenarios**:
  ```
  Scenario: Market analyst prompt mentions TA-Lib indicators
    Tool: Bash (grep)
    Steps:
      1. grep "OBV\|ADX\|MFI\|candlestick\|TA-Lib" tradingagents/agents/analysts/market_analyst.py
    Expected Result: Matches found for new indicators
    Evidence: .sisyphus/evidence/task-4-prompt.txt
  ```

  **Commit**: YES
  - Message: `docs(market): update indicator catalog for TA-Lib 90+ features`
  - Files: `tradingagents/agents/analysts/market_analyst.py`

- [x] 5. **Tests for FeatureCalculator + cache**

  **What to do**:
  - Create `tests/test_feature_calculator.py`:
  - Test FeatureCalculator with mock OHLCV data
  - Test all 29 indicators compute without NaN for valid data
  - Test indicator name mapping (STOCKSTATS_TO_TALIB)
  - Test TA-Lib unavailable fallback
  - Test caching: cache hit, cache miss, cache expiry
  - Test fundamental data cache TTL behavior
  - Test get_indicators end-to-end with TA-Lib path

  **Recommended Agent Profile**: `deep`
  **Parallelization**: After Task 4
  **Blocked By**: Tasks 1, 2, 3

  **Commit**: YES
  - Message: `test(data): add FeatureCalculator and yfinance cache tests`
  - Files: `tests/test_feature_calculator.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [x] F1. **Full Test Suite** — `unspecified-high`
  Run `.venv/bin/python -m pytest tests/ -ra -q`. All 266+ tests must pass. Verify no regressions from stockstats→TA-Lib switch.
  Output: `Tests [N pass/N fail] | VERDICT: APPROVE/REJECT`

- [x] F2. **Performance Benchmark** — `unspecified-high`
  Run market analysis with TA-Lib path and measure:
  - Time for `get_indicators` (all 29 indicators): should be < 1s (was ~2s per indicator)
  - Time for `get_fundamentals` with warm cache: should be < 0.1s (was ~2s for API call)
  - Total analyst phase wall-clock: should be < 15s (was ~30s for sequential)
  Output: `Indicators [N ms] | Fundamentals [N ms] | TOTAL [N s] | VERDICT`

---

## Commit Strategy

- **1**: `feat(data): add TA-Lib FeatureCalculator with 90+ indicators` — `tradingagents/dataflows/feature_calculator.py`, `pyproject.toml`
- **2**: `perf(data): add 24h disk cache for yfinance fundamental data` — `tradingagents/dataflows/y_finance.py`, `tradingagents/default_config.py`
- **3**: `feat(indicators): replace stockstats with TA-Lib FeatureCalculator` — `tradingagents/agents/utils/technical_indicators_tools.py`
- **4**: `docs(market): update indicator catalog for TA-Lib 90+ features` — `tradingagents/agents/analysts/market_analyst.py`
- **5**: `test(data): add FeatureCalculator and yfinance cache tests` — `tests/test_feature_calculator.py`

---

## Success Criteria

### Verification Commands
```bash
.venv/bin/python -m pytest tests/ -q                           # All pass
python -c "from tradingagents.dataflows.feature_calculator import FeatureCalculator; print('OK')"
python -c "from tradingagents.agents.utils.technical_indicators_tools import get_indicators; print(get_indicators('SPY', 'rsi', '2024-01-15'))"
```

### Final Checklist
- [ ] TA-Lib FeatureCalculator integrated, 90+ features computed in one pass
- [ ] get_indicators returns TA-Lib values with stockstats fallback
- [ ] yfinance fundamental data cached to disk with 24h TTL
- [ ] Market analyst prompt updated for richer indicators
- [ ] All 266+ tests pass
- [ ] Indicator computation 10x faster than stockstats
- [ ] No redundant API calls for fundamental data within 24h window
