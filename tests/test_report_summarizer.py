import pytest
from tradingagents.agents.utils.report_summarizer import summarize_reports

def test_summarize_reports():
    state = {
        "market_report": "Signal: Bullish\n- Fact 1\n- Fact 2\nRisk: High\nTarget: 150",
        "sentiment_report": "Direction: Bearish\n* Fact A\nAlert: None\nTarget: 100",
        "news_report": "",
        "fundamentals_report": "Signal: Bullish\n- Growth\nRisk: Low\nPT: 200"
    }
    
    result = summarize_reports(state)
    
    assert "market_summary" in result
    assert "Bullish" in result["market_summary"]
    assert "Fact 1" in result["market_summary"]
    assert "150" in result["market_summary"]
    
    assert "news_summary" in result
    assert result["news_summary"] == "No report available."
