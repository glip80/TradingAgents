# Full Token Optimization Plan — TradingAgents

## TL;DR

> **Quick Summary**: After quick-wins (~35% token reduction), deploy three medium-effort changes to reach the full ~63% token reduction target: report summarizer module, compressed debate history, and early-exit logic. Final target: ~48K input tokens per run (down from ~129K).

> **Deliverables**:
> - `tradingagents/agents/utils/report_summarizer.py` — structured extraction from analyst reports
> - Updated debater/researcher prompts using summaries instead of raw reports
> - `tradingagents/graph/conditional_logic.py` — consensus-based early exit
> - `tradingagents/agents/managers/research_manager.py` — compressed history input
> - Tests for report_summarizer module

> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Task 1 → Task 2-7 → Task 8-9

---

## Context

### Original Request
Full review of TradingAgents execution flow for performance and token usage improvements.

### Interview Summary
**Key Discussions**:
- Quick wins (separate plan) handle: concurrency, indicator trim, risk round decoupling. Saves ~35% tokens.
- Remaining token wasters: report injection into debate (15-25K savings possible), debate history growth (5-10K), no early exit (5-15K).
- Target: ~48K input tokens per run (current ~129K, after quick-wins ~84K, after full plan ~48K).

**Research Findings**:
- All 4 analyst reports (market_report, sentiment_report, news_report, fundamentals_report) are injected verbatim into researcher/debater prompts via f-string interpolation
- Each report is 1000-4000 tokens of LLM-generated prose
- Reports are injected 15+ times per run (6 debate calls + 9 risk calls)
- Debate history accumulates as plain string concatenation — no summarization
- Conditional logic uses count-based termination only: `count >= 2 * max_debate_rounds`

### Token Budget After Quick Wins

| Phase | Original | After Quick Wins | After Full Plan |
|-------|----------|------------------|-----------------|
| Analysts | ~20,000 | ~18,000 | ~18,000 |
| Debate | ~33,000 | ~33,000 | ~10,000 |
| Research Mgr | ~4,300 | ~4,300 | ~2,500 |
| Trader | ~1,500 | ~1,500 | ~1,000 |
| Risk Debate | ~63,000 | ~21,000 (1 round) | ~10,000 (summaries) |
| Portfolio Mgr | ~8,500 | ~8,500 | ~4,000 |
| **Total** | **~129,000** | **~86,000** | **~46,000** |

---

## Work Objectives

### Core Objective
Reduce token budget to ~48K by replacing raw-report injection with structured summaries, compressing debate history, and adding consensus-based early exit.

### Concrete Deliverables
- New: `tradingagents/agents/utils/report_summarizer.py`
- Modified: `tradingagents/agents/researchers/bull_researcher.py`
- Modified: `tradingagents/agents/researchers/bear_researcher.py`
- Modified: `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- Modified: `tradingagents/agents/risk_mgmt/conservative_debator.py`
- Modified: `tradingagents/agents/risk_mgmt/neutral_debator.py`
- Modified: `tradingagents/agents/managers/research_manager.py`
- Modified: `tradingagents/graph/conditional_logic.py`
- New: `tests/test_report_summarizer.py`

### Definition of Done
- [ ] Report summarizer extracts from each report: recommendation direction, key facts (3-5), risk flags, confidence level
- [ ] Researcher/debater prompts use `{market_summary}` etc. instead of `{market_research_report}`
- [ ] Research Manager sees compressed debate history (last round key arguments, not full transcript)
- [ ] Debate early-exits when bull + bear agree on direction (both buy/hold/sell)
- [ ] All existing + new tests pass

### Must Have
- Summary must preserve: directional signal, price target (if mentioned), key catalysts, key risks
- Early exit must be opt-in (config flag) and respect max_debate_rounds as ceiling
- Report summarizer must handle crypto-adapted reports (no company fundamentals available)
- Full reports still saved to state/logging — summaries are additional, not replacement

### Must NOT Have (Guardrails)
- Must NOT remove raw reports from state — `market_report`, `sentiment_report` etc. preserved
- Must NOT add a separate LLM call for summarization — use LLM-free extraction or a single lightweight call
- Must NOT change the graph topology — same nodes, same edges
- Must NOT hallucinate in summaries — extraction must be deterministic where possible, LLM-assisted only for semantic understanding

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after for report_summarizer module
- **Framework**: pytest

### QA Policy
Every task includes agent-executed QA scenarios.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation):
├── Task 1: Report summarizer module [deep]

Wave 2 (After Task 1 — 6 parallel agent updates):
├── Task 2: Bull researcher → use summaries [quick]
├── Task 3: Bear researcher → use summaries [quick]
├── Task 4: Aggressive debator → use summaries [quick]
├── Task 5: Conservative debator → use summaries [quick]
├── Task 6: Neutral debator → use summaries [quick]
├── Task 7: Research manager → compressed history [quick]

Wave 3 (After Task 2-7 — state-flow changes):
├── Task 8: Early-exit debate logic [quick]
├── Task 9: Propagate summaries through graph state [quick]

Wave 4 (After ALL — verification):
└── Task 10: Report summarizer tests [deep]

Wave FINAL:
├── Task F1: Full test suite [unspecified-high]
├── Task F2: Token count verification [unspecified-high]
└── Task F3: Decision quality comparison [deep]
```

**Critical Path**: Task 1 → Task 2-7 (parallel) → Task 8-9 → F1-F3
**Max Concurrent**: 6 (Wave 2)

---

## TODOs

- [ ] 1. **Report summarizer module** (`tradingagents/agents/utils/report_summarizer.py`)

  **What to do**:
  - Create new module with function `summarize_reports(state: dict) -> dict[str, str]`
  - Input: `state["market_report"]`, `state["sentiment_report"]`, `state["news_report"]`, `state["fundamentals_report"]`
  - For each report, extract structured data conservatively:
    - Directional signal: Buy/Bullish | Sell/Bearish | Hold/Neutral/Mixed — regex-based first, fall back to keyword heuristics
    - Key facts: 3-5 bullet points extracted from the report body
    - Risk flags: any mention of "risk", "volatility", "uncertainty", "threat", "concern"
    - Price target: if mentioned as a number with currency symbol
  - Return dict: `{"market_summary": "...", "sentiment_summary": "...", "news_summary": "...", "fundamentals_summary": "..."}`
  - Each summary ≤ 200 tokens
  - Store in state as new keys: `state["market_summary"] = ...`

  **Implementation approach**:
  - NO LLM call — deterministic extraction using regex, keyword matching, and heuristics
  - Pattern: look for section headers (e.g., "**Recommendation**:", "**Rating**:", "FINAL TRANSACTION PROPOSAL:")
  - Fallback: if pattern extraction yields nothing, take first 3 sentences as summary
  - Handle crypto reports: `fundamentals_summary` = "N/A: fundamentals unavailable for crypto" when `fundamentals_report` contains "unavailable" or is empty

  **Must NOT do**:
  - Do NOT make an LLM call for summarization — this would negate the token savings
  - Do NOT modify the raw report strings in state
  - Do NOT add new dependencies beyond stdlib + `re`

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: `[]`
  - Reason: New module with regex/heuristic extraction logic. Multiple edge cases (empty reports, crypto, non-English, malformed markdown).

  **Parallelization**: Sequential (blocks Tasks 2-9)
  **Blocks**: Tasks 2, 3, 4, 5, 6, 7, 9
  **Blocked By**: None

  **References**:
  - `tradingagents/agents/utils/agent_utils.py` — sibling utility module (pattern to follow for module structure)
  - `tradingagents/agents/utils/rating.py` — parse_rating function (similar pattern: regex-based extraction from markdown)
  - `tradingagents/agents/analysts/sentiment_analyst.py:99-165` — `_build_system_message` (shows report structure with section headers)
  - Report state keys: `market_report`, `sentiment_report`, `news_report`, `fundamentals_report`
  - State accessed in: `bull_researcher.py:11-14`, `aggressive_debator.py:13-16` (pattern to follow)

  **QA Scenarios**:
  ```
  Scenario: Extracts BUY recommendation from structured report
    Tool: Bash (python REPL)
    Preconditions: Mock state with market_report = "**Recommendation**: BUY\nConfidence: High\nKey facts..."
    Steps:
      1. Import summarize_reports
      2. Call with mock state
      3. Assert market_summary contains "BUY"
      4. Assert token count < 200
    Expected Result: Summary captures direction + key facts
    Evidence: .sisyphus/evidence/task-1-buy-extract.txt

  Scenario: Handles crypto with unavailable fundamentals
    Tool: Bash (python REPL)
    Preconditions: Mock state with fundamentals_report = "Fundamentals may be unavailable for crypto"
    Steps:
      1. Call summarize_reports with crypto-flagged state
      2. Assert fundamentals_summary contains "unavailable" or "N/A"
    Expected Result: Graceful degradation for crypto
    Evidence: .sisyphus/evidence/task-1-crypto.txt

  Scenario: Empty report produces safe default
    Tool: Bash (python REPL)
    Preconditions: Mock state with empty market_report = ""
    Steps:
      1. Call summarize_reports
      2. Assert market_summary is not empty, not "None", not crash
    Expected Result: Safe default string, no exception
    Evidence: .sisyphus/evidence/task-1-empty-report.txt
  ```

  **Commit**: YES
  - Message: `perf(agents): add deterministic report summarizer for debate input`
  - Files: `tradingagents/agents/utils/report_summarizer.py`

- [ ] 2. **Bull researcher → use summaries**

  **What to do**:
  - In `tradingagents/agents/researchers/bull_researcher.py`:
  - Replace `{market_research_report}` → `{market_summary}` (and same for sentiment, news, fundamentals)
  - Read new state keys: `state["market_summary"]`, `state["sentiment_summary"]`, `state["news_summary"]`, `state["fundamentals_summary"]`
  - Fallback: if summary keys don't exist (e.g., summarizer not run), fall back to raw report keys
  - Same pattern: `report = state.get("market_summary") or state["market_report"]`

  **Must NOT do**:
  - Do NOT remove the old `{market_research_report}` template variable — keep it as fallback

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**: Can run in parallel with Tasks 3, 4, 5, 6, 7
  **Blocked By**: Task 1

  **References**:
  - `tradingagents/agents/researchers/bull_researcher.py:11-14` — where reports are read from state
  - `tradingagents/agents/researchers/bull_researcher.py:33-38` — where reports are interpolated into prompt

  **QA Scenarios**:
  ```
  Scenario: Uses summary when available, falls back to raw
    Tool: Bash (pytest)
    Steps:
      1. Import bull_node function
      2. Mock state with both market_summary and market_report
      3. Verify prompt contains summary text, not full report
    Expected Result: Summary used, raw report not in prompt
    Evidence: .sisyphus/evidence/task-2-summary-used.txt
  ```

  **Commit**: YES
  - Message: `perf(bull): use report summaries instead of raw reports`
  - Files: `tradingagents/agents/researchers/bull_researcher.py`

- [ ] 3. **Bear researcher → use summaries**

  **What to do**:
  - Same as Task 2 but for `tradingagents/agents/researchers/bear_researcher.py`

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Parallel with Tasks 2, 4, 5, 6, 7
  **Blocked By**: Task 1

  **QA Scenarios**: Same pattern as Task 2 — verify summary used.
  **Commit**: YES — `perf(bear): use report summaries instead of raw reports`

- [ ] 4. **Aggressive debator → use summaries**

  **What to do**:
  - Same pattern as Task 2 but for `tradingagents/agents/risk_mgmt/aggressive_debator.py`

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Parallel with Tasks 2, 3, 5, 6, 7
  **Blocked By**: Task 1

  **Commit**: YES — `perf(risk): use report summaries in aggressive debator`

- [ ] 5. **Conservative debator → use summaries**

  **What to do**:
  - Same as Task 2 for `tradingagents/agents/risk_mgmt/conservative_debator.py`

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Parallel with Tasks 2, 3, 4, 6, 7
  **Blocked By**: Task 1

  **Commit**: YES — `perf(risk): use report summaries in conservative debator`

- [ ] 6. **Neutral debator → use summaries**

  **What to do**:
  - Same as Task 2 for `tradingagents/agents/risk_mgmt/neutral_debator.py`

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Parallel with Tasks 2, 3, 4, 5, 7
  **Blocked By**: Task 1

  **Commit**: YES — `perf(risk): use report summaries in neutral debator`

- [ ] 7. **Research manager → compressed history**

  **What to do**:
  - In `tradingagents/agents/managers/research_manager.py`:
  - Instead of passing `{history}` (full debate transcript), pass condensed version
  - Add helper: `_compress_debate_history(history: str) -> str` — extracts key arguments from each round
  - Pattern: find "Bull Analyst:" and "Bear Analyst:" prefixes, extract 1-2 sentences after each
  - Also use summary state keys instead of raw reports when present

  **Must NOT do**:
  - Do NOT remove the full history from state — just compress for prompt injection
  - Do NOT lose the rating scale or debate context

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**: Parallel with Tasks 2, 3, 4, 5, 6
  **Blocked By**: Task 1

  **References**:
  - `tradingagents/agents/managers/research_manager.py:21` — where history is read
  - `tradingagents/agents/managers/research_manager.py:25-43` — prompt template with {history}

  **QA Scenarios**:
  ```
  Scenario: Compressed history is shorter than full
    Tool: Bash (python REPL)
    Steps:
      1. Feed mock debate history (3 rounds, ~3000 chars)
      2. Call _compress_debate_history
      3. Assert result < 800 chars
    Expected Result: Significant compression
    Evidence: .sisyphus/evidence/task-7-compression.txt
  ```

  **Commit**: YES
  - Message: `perf(manager): compress debate history for research manager`
  - Files: `tradingagents/agents/managers/research_manager.py`

- [ ] 8. **Early-exit debate logic**

  **What to do**:
  - In `tradingagents/graph/conditional_logic.py`: add `_detect_consensus(state)` helper
  - Logic: extract last bull response and last bear response. If both contain the same recommendation direction (BUY/Bullish vs SELL/Bearish), consensus reached.
  - Detection: regex for "BUY" vs "SELL" (or equivalents) in the last response content
  - In `should_continue_debate()`: if `_detect_consensus(state)` is True AND at least 1 round completed, route to "Research Manager" regardless of count
  - Respect `max_debate_rounds` as ceiling — early exit never OVERRIDES max rounds, just enables earlier exit
  - Add config flag: `"debate_early_exit": True` in `DEFAULT_CONFIG`

  **Must NOT do**:
  - Do NOT exit before at least 1 full round (both bull and bear have spoken)
  - Do NOT exit on "Hold" recommendations (ambiguous — needs more debate)
  - Do NOT change the count-based termination — early exit is additional, not replacement

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: `[]`

  **Parallelization**: Can run in parallel with Task 9
  **Blocked By**: Tasks 2, 3, 7

  **References**:
  - `tradingagents/graph/conditional_logic.py:52-61` — `should_continue_debate`
  - `tradingagents/graph/conditional_logic.py:9-11` — `max_debate_rounds` init
  - `tradingagents/default_config.py` — where to add `"debate_early_exit": True`

  **QA Scenarios**:
  ```
  Scenario: Consensus exits early
    Tool: Bash (pytest)
    Preconditions: Mock state with bull="BUY" + bear="SELL" → no consensus
    Steps:
      1. Test should_continue_debate with 1 round completed, no consensus
      2. Assert returns "Bear Researcher" (continues)
      3. Test with both = "BUY" → consensus
      4. Assert returns "Research Manager" (early exit)
    Expected Result: Consensus detected, early exit triggered
    Evidence: .sisyphus/evidence/task-8-consensus.txt

  Scenario: No consensus, respects max rounds
    Tool: Bash (pytest)
    Steps:
      1. Test with 0 consensus, count at max
      2. Assert returns "Research Manager" (normal termination)
    Expected Result: Normal path works, early exit doesn't break
    Evidence: .sisyphus/evidence/task-8-no-consensus.txt

  Scenario: Config flag disables early exit
    Tool: Bash (pytest)
    Steps:
      1. Set debate_early_exit=False
      2. Test with consensus true
      3. Assert continues normally (ignores consensus)
    Expected Result: Early exit opt-in via config
    Evidence: .sisyphus/evidence/task-8-config-flag.txt
  ```

  **Commit**: YES
  - Message: `feat(debate): add consensus-based early exit to debate loop`
  - Files: `tradingagents/graph/conditional_logic.py`, `tradingagents/default_config.py`

- [ ] 9. **Propagate summaries through graph state**

  **What to do**:
  - In `tradingagents/graph/setup.py` or the propogator: after all analysts complete, run `summarize_reports(state)`
  - Store summaries in state under new keys: `market_summary`, `sentiment_summary`, `news_summary`, `fundamentals_summary`
  - This ensures all downstream agents (Tasks 2-7) can read summaries
  - Hook: add a state update after the last analyst node completes, before the debate section starts
  - Alternative: run summarizer lazily in each agent (first access triggers, then cached in state)

  **Implementation approach**: Lazy approach — each agent does `state.get("market_summary") or summarize_reports(state)["market_summary"]` on first access. This avoids: adding a graph node, changing graph topology, running summarizer when it won't be used.

  **Must NOT do**:
  - Do NOT add a new graph node — keep topology unchanged
  - Do NOT run summarizer if summaries already exist in state

  **Recommended Agent Profile**: `quick`
  **Parallelization**: Can run in parallel with Task 8
  **Blocked By**: Tasks 1, 2

  **References**:
  - `tradingagents/graph/setup.py:59-68` — where agent nodes are created
  - State flow: `analysts → debate → research_mgr → trader → risk → portfolio_mgr`

  **QA Scenarios**:
  ```
  Scenario: Summaries generated once, reused across agents
    Tool: Bash (pytest integration test)
    Steps:
      1. Run mini graph with 1 analyst
      2. Verify state has summary keys after analyst completes
      3. Verify debate nodes read summaries from state
    Expected Result: Summaries present and used
    Evidence: .sisyphus/evidence/task-9-propagation.txt
  ```

  **Commit**: YES
  - Message: `perf(state): propagate report summaries through graph state`
  - Files: `tradingagents/agents/utils/report_summarizer.py` (add lazy load), agent files (add fallback)

- [ ] 10. **Report summarizer tests**

  **What to do**:
  - Create `tests/test_report_summarizer.py`
  - Test cases:
    1. Structured report with explicit recommendation → correct extraction
    2. Empty report → safe default
    3. Crypto fundamentals report → "unavailable" summary
    4. All 4 report types in one call → dict with 4 keys
    5. Token count per summary < 200
    6. Non-English report → still produces meaningful extraction
    7. Malformed markdown → doesn't crash
    8. Report with no clear recommendation → "Neutral" default

  **Must NOT do**:
  - Do not test LLM-dependent behavior (summarizer is deterministic)

  **Recommended Agent Profile**: `deep`
  **Parallelization**: After Task 9
  **Blocked By**: Task 1

  **Commit**: YES
  - Message: `test(summarizer): add comprehensive report summarizer tests`
  - Files: `tests/test_report_summarizer.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

- [ ] F1. **Full Test Suite** — `unspecified-high`
  Run `.venv/bin/python -m pytest tests/ -ra -q`. All 266+ existing tests + new summarizer tests must pass.
  Output: `Tests [N pass/N fail] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Token Count Verification** — `unspecified-high`
  Run CLI with depth=3, risk-depth=1, capture LLM event logs. Verify:
  - Per-debate-call input < 2000 tokens (was ~4500)
  - Per-risk-call input < 2000 tokens (was ~5500)
  - Total run input < 55K tokens
  Output: `Debate [N tokens/call] | Risk [N tokens/call] | Total [N] | VERDICT`

- [ ] F3. **Decision Quality Comparison** — `deep`
  Run analysis on same ticker/date with OLD (raw reports) and NEW (summaries). Compare:
  - Final recommendation direction (same? disagree?)
  - Portfolio Manager executive summary content overlap
  - Key facts mentioned in both runs
  Output: `Direction [SAME/DIFF] | Facts shared [N/N] | VERDICT`

---

## Commit Strategy

- **1**: `perf(agents): add deterministic report summarizer for debate input` — `tradingagents/agents/utils/report_summarizer.py`
- **2**: `perf(bull): use report summaries instead of raw reports` — `tradingagents/agents/researchers/bull_researcher.py`
- **3**: `perf(bear): use report summaries instead of raw reports` — `tradingagents/agents/researchers/bear_researcher.py`
- **4**: `perf(risk): use report summaries in aggressive debator` — `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- **5**: `perf(risk): use report summaries in conservative debator` — `tradingagents/agents/risk_mgmt/conservative_debator.py`
- **6**: `perf(risk): use report summaries in neutral debator` — `tradingagents/agents/risk_mgmt/neutral_debator.py`
- **7**: `perf(manager): compress debate history for research manager` — `tradingagents/agents/managers/research_manager.py`
- **F1-F3**: Individual verification commits per review pass

---

## Success Criteria

### Verification Commands
```bash
.venv/bin/python -m pytest tests/ -q                    # All pass
.venv/bin/python -m pytest tests/test_report_summarizer.py -v  # Summarizer tests pass
```

### Final Checklist
- [ ] Report summarizer extracts direction + key facts + risks from all 4 report types
- [ ] All 6 agent prompts (bull, bear, 3 debaters, research_manager) use summaries
- [ ] Fallback to raw reports when summaries unavailable (backward compat)
- [ ] Full reports still saved to state/logging
- [ ] Token-per-call metrics verified below targets
- [ ] Decision quality comparable between old and new runs
- [ ] All 266+ tests pass

