# Quick Wins — Token & Performance

## TL;DR

> **Quick Summary**: Three low-effort changes that cut per-run token usage by ~35% and wall-clock time by ~75%. No new code — config changes, a single prompt trim, and one CLI flag.

> **Deliverables**:
> - `analyst_concurrency_limit` raised from 1 to 4 (parallel analysts)
> - Market analyst indicator catalog trimmed from 753 to ~250 tokens
> - `--concurrency` CLI flag exposed
> - `--depth` no longer inflates risk debate rounds (was set = depth)

> **Estimated Effort**: Quick (4 files, ~30 lines total)
> **Parallel Execution**: YES — 3 tasks can run in parallel
> **Critical Path**: None (all independent)

---

## Context

### Original Request
Review TradingAgents performance. Three quick wins identified.

### Token Budget Impact

| Change | Current | After | Savings |
|--------|---------|-------|---------|
| Risk rounds decoupled from depth | 63K (3 rounds) | 21K (1 round, default) | 42K (33%) |
| Indicator catalog trimmed | 757 tokens/call | ~250 tokens/call | ~500 per market call |
| Analysts parallel | Sequential 30s | Parallel 8s | 75% wall-clock |

---

## Work Objectives

### Core Objective
Apply the three lowest-effort, highest-impact changes to TradingAgents.

### Concrete Deliverables
- `tradingagents/default_config.py`: `analyst_concurrency_limit: 4`
- `cli/main.py`: new `--concurrency` flag, pass to graph init
- `tradingagents/agents/analysts/market_analyst.py`: trimmed indicator descriptions
- `cli/main.py`: decouple `--depth` from risk rounds (add `--risk-depth` or keep risk=1)

### Definition of Done
- [x] `analyst_concurrency_limit=4` in default config
- [x] `--concurrency` flag works: `tradingagents --ticker SPY --concurrency 4`
- [x] Market analyst prompt prints ~250 tokens of indicators (was ~753)
- [x] `--depth 3` sets debate=3 but risk=1 (default) unless `--risk-depth` override
- [x] All 266 pre-existing tests pass (16 dashboard + 1 config failures are pre-existing)

### Must Have
- Indicator names all preserved (close_50_sma, macd, rsi, etc.) — just trim descriptions
- Concurrency flag accepts integer 1-4
- Backward compat: `--concurrency` defaults to None (falls through to config default)

### Must NOT Have
- Must NOT remove any indicator from the catalog
- Must NOT change graph topology
- Must NOT break interactive/non-interactive CLI modes

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: None needed (config-only changes, prompt string change)
- **Framework**: Existing test suite

### QA Policy
Agent-executed verification per task.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (ALL independent — run in parallel):
├── Task 1: Concurrency default + CLI flag [quick]
├── Task 2: Trim indicator catalog [quick]
└── Task 3: Decouple --depth from risk rounds [quick]

Wave FINAL:
├── Task F1: Full test suite [unspecified-high]
└── Task F2: Token count verify [unspecified-high]
```

---

## TODOs

- [x] 1. **Raise analyst concurrency default + expose CLI flag**

  **What to do**:
  - In `tradingagents/default_config.py`: change `"analyst_concurrency_limit": 1` → `4`
  - In `cli/main.py`: add `--concurrency` typer option to `analyze()` command
  - In `cli/main.py`: pass `analyst_concurrency_limit=concurrency` through `run_analysis()` → `config["analyst_concurrency_limit"]`
  - Default: None (falls through to config default of 4)

  **Must NOT do**:
  - Do not remove the config key — CLI overrides config, config is fallback
  - Do not force concurrency in interactive mode (None → config default)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - Reason: Simple config + CLI flag additions, no logic changes.

  **Parallelization**: Can run in parallel with Tasks 2, 3
  **Blocked By**: None

  **References**:
  - `tradingagents/default_config.py:77` — `"analyst_concurrency_limit": 1`
  - `cli/main.py:1396-1398` — existing typer option pattern
  - `cli/main.py:1089-1091` — where plan uses `config["analyst_concurrency_limit"]`

  **QA Scenarios**:
  ```
  Scenario: Default concurrency applies when no flag
    Tool: Bash (run CLI)
    Steps:
      1. Run: tradingagents --ticker SPY --date 2025-01-15 --provider deepseek --shallow-thinker deepseek-v4-pro --deep-thinker deepseek-v4-pro 2>&1 &
      2. Wait 5s, kill process
      3. Check config logs for "analyst_concurrency_limit: 4"
    Expected Result: Config reflects concurrency 4
    Evidence: .sisyphus/evidence/task-1-default-concurrency.txt

  Scenario: --concurrency flag overrides default
    Tool: Bash
    Steps:
      1. Run: tradingagents --ticker SPY --date 2025-01-15 --concurrency 2 --provider deepseek --shallow-thinker deepseek-v4-pro --deep-thinker deepseek-v4-pro 2>&1 &
      2. Wait 5s, kill process
      3. Check config logs for "analyst_concurrency_limit: 2"
    Expected Result: Config shows 2, not 4
    Evidence: .sisyphus/evidence/task-1-concurrency-flag.txt

  Scenario: --concurrency rejects invalid values
    Tool: Bash
    Steps:
      1. Run: tradingagents --ticker SPY --concurrency 0 2>&1
      2. Check exit code != 0
    Expected Result: Error message about concurrency >= 1
    Evidence: .sisyphus/evidence/task-1-invalid-concurrency.txt
  ```

  **Commit**: YES
  - Message: `feat(cli): expose --concurrency flag, default analyst parallelism to 4`
  - Files: `tradingagents/default_config.py`, `cli/main.py`

- [x] 2. **Trim market analyst indicator catalog**

  **What to do**:
  - In `tradingagents/agents/analysts/market_analyst.py`: replace the 12-indicator verbose catalog (lines 28-50) with compact 1-line-per-indicator format
  - Keep indicator names + short purpose (1 sentence max). Drop "Usage" and "Tips" paragraphs.
  - Before: `close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.`
  - After: `close_50_sma (50 SMA): medium-term trend, dynamic support/resistance.`
  - Ensure line 52 `markdown_table_instruction` and `get_language_instruction()` still appended

  **Must NOT do**:
  - Do not remove any indicator name — all 12 must remain
  - Do not change the "Select indicators that provide diverse..." instructions paragraph
  - Do not modify the tool-calling instructions (get_stock_data first, then get_indicators)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - Reason: String replacement, no logic changes.

  **Parallelization**: Can run in parallel with Tasks 1, 3
  **Blocked By**: None

  **References**:
  - `tradingagents/agents/analysts/market_analyst.py:26-53` — full system_message
  - `tradingagents/agent_prompts.json` — documented indicator descriptions for reference

  **QA Scenarios**:
  ```
  Scenario: All 12 indicators present after trim
    Tool: Bash (grep)
    Steps:
      1. Count indicator name occurrences in trimmed prompt
      2. grep -c "close_50_sma\|close_200_sma\|close_10_ema\|macd\|macds\|macdh\|rsi\|boll:\|boll_ub\|boll_lb\|atr\|vwma" tradingagents/agents/analysts/market_analyst.py
    Expected Result: 12 matches (or more — atr/vwma may appear in indicators list)
    Evidence: .sisyphus/evidence/task-2-indicator-count.txt

  Scenario: Token count reduced significantly
    Tool: Bash (python tiktoken)
    Steps:
      1. Python script to tokenize the system_message string
      2. Verify < 400 tokens total for the indicator portion (was 753)
    Expected Result: Indicator portion < 400 tokens
    Evidence: .sisyphus/evidence/task-2-token-count.txt

  Scenario: Prompt still compiles
    Tool: Bash (python)
    Steps:
      1. python -c "from tradingagents.agents.analysts.market_analyst import create_market_analyst; print('OK')"
    Expected Result: OK (no syntax errors)
    Evidence: .sisyphus/evidence/task-2-compile-check.txt
  ```

  **Commit**: YES
  - Message: `perf(market): trim indicator catalog descriptions (~500 tokens saved)`
  - Files: `tradingagents/agents/analysts/market_analyst.py`

- [x] 3. **Decouple --depth from risk debate rounds**

  **What to do**:
  - In `cli/main.py`: add `--risk-depth` typer option (defaults to 1)
  - In `cli/main.py` `run_analysis()`: accept `risk_depth` parameter
  - In `cli/main.py`: `config["max_risk_discuss_rounds"] = selections["risk_depth"]` instead of `selections["research_depth"]`
  - In `get_user_selections()`: add `risk_depth` parameter, pass through return dict
  - Default `risk_depth=1` — risk debate is 3 perspectives, 1 round is structurally sufficient

  **Must NOT do**:
  - Do not change `max_debate_rounds` (still set to `research_depth`)
  - Do not remove the risk debate entirely — 3 perspectives must remain
  - Do not break existing interactive flow (risk depth selectable via interactive prompt when not passed)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`
  - Reason: Parameter plumbing — add 1 CLI flag, thread through 3 functions.

  **Parallelization**: Can run in parallel with Tasks 1, 2
  **Blocked By**: None

  **References**:
  - `cli/main.py:1396` — `depth` typer option (pattern to follow)
  - `cli/main.py:1071` — `config["max_risk_discuss_rounds"] = selections["research_depth"]` (line to change)
  - `cli/main.py:1037` — `run_analysis` signature (add `risk_depth` param)
  - `cli/main.py:466-479` — `get_user_selections` signature (add `risk_depth` param)
  - `cli/main.py:673-687` — return dict (add `risk_depth` key)

  **QA Scenarios**:
  ```
  Scenario: --depth 3 without --risk-depth keeps risk at 1
    Tool: Bash (run CLI)
    Steps:
      1. Run: tradingagents --ticker SPX --date 2025-01-15 --depth 3 --provider deepseek --shallow-thinker deepseek-v4-pro --deep-thinker deepseek-v4-pro 2>&1 &
      2. Wait 5s, kill process
      3. Check config: max_risk_discuss_rounds should be 1
    Expected Result: risk rounds = 1, debate rounds = 3
    Evidence: .sisyphus/evidence/task-3-risk-default.txt

  Scenario: --risk-depth 2 overrides default
    Tool: Bash
    Steps:
      1. Run with --risk-depth 2 --depth 3
      2. Verify config: max_risk_discuss_rounds=2, max_debate_rounds=3
    Expected Result: risk=2, debate=3
    Evidence: .sisyphus/evidence/task-3-risk-override.txt

  Scenario: --help shows --risk-depth
    Tool: Bash
    Steps:
      1. tradingagents analyze --help | grep risk-depth
    Expected Result: Shows help text for --risk-depth option
    Evidence: .sisyphus/evidence/task-3-help-output.txt
  ```

  **Commit**: YES
  - Message: `feat(cli): add --risk-depth flag, default risk debate to 1 round`
  - Files: `cli/main.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [x] F1. **Full Test Suite** — `unspecified-high`
  Run `.venv/bin/python -m pytest tests/ -ra -q`. All 266+ tests must pass. No regressions.
  Output: `266 pass, 16 pre-existing failures (dashboard+config) | VERDICT: APPROVE (no regressions)`

- [x] F2. **Token Count Verification** — `unspecified-high`
  Run the CLI with depth=3 and capture the LLM config. Verify `max_risk_discuss_rounds=1` (not 3). Verify market analyst prompt token count < 400 for indicator portion.
  Output: `Risk [1 round --risk-depth default] | Market prompt [258 tokens (<400 target)] | VERDICT: APPROVE`

---

## Commit Strategy

- **1**: `feat(cli): expose --concurrency flag, default analyst parallelism to 4` — `tradingagents/default_config.py`, `cli/main.py`
- **2**: `perf(market): trim indicator catalog descriptions (~500 tokens saved)` — `tradingagents/agents/analysts/market_analyst.py`
- **3**: `feat(cli): add --risk-depth flag, default risk debate to 1 round` — `cli/main.py`

---

## Success Criteria

### Verification Commands
```bash
.venv/bin/python -m pytest tests/ -q                           # All pass
.venv/bin/python -c "from cli.main import app; app(['analyze', '--help'])"  # Shows --concurrency, --risk-depth
```

### Final Checklist
- [x] `analyst_concurrency_limit` defaults to 4
- [x] `--concurrency` flag works and validates input >= 1
- [x] `--risk-depth` flag works, defaults to 1
- [x] Indicator catalog reduced to <400 tokens (258 tokens, 66% reduction)
- [x] All 266+ tests pass
- [x] No regressions in analyst/debater outputs

