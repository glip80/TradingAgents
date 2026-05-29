"""Deterministic summary extraction from analyst reports.

Extracts structured information (signals, facts, risks, targets) from raw 
report strings using heuristics and regex.
"""

import re

def summarize_reports(state: dict) -> dict[str, str]:
    """Extract summaries from raw reports in state."""
    summaries = {}
    
    # Keys to process
    keys = {
        "market_report": "market_summary",
        "sentiment_report": "sentiment_summary",
        "news_report": "news_summary",
        "fundamentals_report": "fundamentals_summary"
    }
    
    for input_key, output_key in keys.items():
        report = state.get(input_key, "")
        summaries[output_key] = _extract_report_summary(report)
        
    return summaries

def _extract_report_summary(text: str) -> str:
    """Deterministic extraction for a single report."""
    if not text:
        return "No report available."
        
    # Heuristic extraction patterns
    signal = _find_signal(text)
    facts = _find_facts(text)
    risks = _find_risks(text)
    target = _find_price_target(text)
    
    return f"Signal: {signal}\nFacts: {facts}\nRisks: {risks}\nTarget: {target}"

def _find_signal(text: str) -> str:
    # Heuristic: match common signal keywords
    patterns = [r"Signal:\s*(\w+)", r"Direction:\s*(\w+)"]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).capitalize()
    return "Neutral"

def _find_facts(text: str) -> str:
    # Look for bullet points or lists
    lines = text.splitlines()
    facts = [line.strip("-* ").strip() for line in lines if line.strip().startswith(("-", "*"))]
    return "; ".join(facts[:3]) if facts else "No key facts extracted."

def _find_risks(text: str) -> str:
    # Look for a 'Risk' or 'Warning' section
    m = re.search(r"(?:Risk|Warning|Alert):\s*(.*)", text, re.IGNORECASE)
    return m.group(1).strip() if m else "None identified."

def _find_price_target(text: str) -> str:
    m = re.search(r"(?:Price Target|Target|PT):\s*[$]?([\d.]+)", text, re.IGNORECASE)
    return m.group(1) if m else "N/A"
