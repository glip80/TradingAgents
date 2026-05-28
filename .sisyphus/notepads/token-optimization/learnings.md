# Token Optimization Plan — Learnings

## Report Structure Patterns
- Analyst reports use markdown with `**Recommendation**:`, `**Rating**:`, `FINAL TRANSACTION PROPOSAL:` section headers
- `rating.py` has regex-based `parse_rating()` function to reference

## State Keys
- Raw reports: `market_report`, `sentiment_report`, `news_report`, `fundamentals_report`
- Summary keys (new): `market_summary`, `sentiment_summary`, `news_summary`, `fundamentals_summary`

## Agent Patterns
- Bull/Bear researchers: read state keys on lines ~11-14, interpolate into prompt on lines ~33-38
- Risk debaters: read state on lines ~13-16

## Task 2: Bull Researcher Summary Integration

### Implementation
- Changed assignments (lines 11-14) to `state.get("market_summary") or state["market_report"]` pattern
- Variable names unchanged — summaries flow into prompt via same `{market_research_report}` etc. f-string placeholders
- Summary keys: `market_summary`, `sentiment_summary`, `news_summary`, `fundamentals_summary`
- Raw reports preserved as fallback when summaries missing

## Key Guardrails
- NO LLM calls for summarization — deterministic regex/heuristics only
- Raw reports preserved in state — summaries are ADDITIONAL
- Early exit requires at least 1 full round completed
## Task 1: Report Summarizer Implementation

### Implementation Decisions
- Used `frozenset` for directional signal lookups (O(1) membership, immutable)
- Split extraction into per-field helpers (`_extract_directional`, `_extract_risk_flags`, etc.)
- Crypto detection: check for "unavailable" OR "not available" OR empty string in fundamentals_report
- Token estimation: simple whitespace split (1 token ≈ 1 word for English)
- Truncation: walk backwards from max_tokens to find sentence boundary for clean cut
- Import isolation: module has NO imports from langchain/other tradingagents submodules — only stdlib (re, typing, math)
  - Required for isolated testing: use `importlib.util.spec_from_file_location()` to load without triggering langchain imports
- `_RATING_LABEL_RE` pattern from rating.py: `r"rating.*?[:\-][\s*]*(\w+)"` — followed similar style for recommendation headers

### Key Patterns
- Section header regex: `r"^\s*\*\*?(?:Recommendation|Rating|FINAL TRANSACTION PROPOSAL)\*\*?[:\s]+(\w+)"` (MULTILINE flag)
- Bull/Bear/Neutral signal sets: `_BUY_SIGNALS`, `_SELL_SIGNALS`, `_HOLD_SIGNALS` as frozensets
- Risk keyword regex: single `\b`-delimited alternation for "risk|risks|risky|volatility|..." — case-insensitive
- Key facts extraction 4-pass: markdown bullets → ordered lists → metric keywords → first sentences fallback

### Verification Results (Task 1)
- BUY extraction: PASS
- Empty report handling: PASS
- Crypto fundamentals: PASS
- State side-effects: PASS
- Token limit (200): PASS
- Price target extraction: PASS
- Risk flags: PASS

### QA Evidence Files
- `.sisyphus/evidence/task-1-buy-extract.txt`
- `.sisyphus/evidence/task-1-crypto.txt`
- `.sisyphus/evidence/task-1-empty-report.txt`
