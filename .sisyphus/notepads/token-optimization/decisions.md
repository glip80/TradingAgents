# Token Optimization — Decisions

## 2026-05-27 | Task 1: Lazy-load summarization
Decision: Each agent will do `state.get("market_summary") or summarize_reports(state)["market_summary"]` on first access. This avoids graph topology changes and unnecessary summarizer runs.

## 2026-05-27 | Task 8: Consensus detection
Decision: Regex-based detection for BUY/BULL vs SELL/BEAR in last bull/bear responses. Hold recommendations do NOT trigger consensus (needs more debate).

## 2026-05-27 | Task 9: Lazy vs Eager summarization
Decision: Lazy approach wins — avoids graph node, doesn't change topology, only runs summarizer when actually needed.