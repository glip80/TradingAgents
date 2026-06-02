"""Integration tests for tradingagents.dataflows.yfinance_news — real yfinance API calls."""

from datetime import datetime, date

import pytest

from tradingagents.dataflows.yfinance_news import (
    _extract_article_data,
    get_news_yfinance,
    get_global_news_yfinance,
)


# Dates chosen to include recent trading days. AAPL+MSFT have daily news flow
# so a 10-day window virtually guarantees at least one article.
TICKER = "AAPL"
START_DATE = (date.today() - date.resolution * 10).isoformat()
END_DATE = date.today().isoformat()


# ---------------------------------------------------------------------------
# _extract_article_data — unit-level, no external calls
# ---------------------------------------------------------------------------

def test_extract_article_data_nested_content():
    """Nested 'content' dict yields correct extracted fields."""
    article = {
        "content": {
            "title": "Apple Reports Record Earnings",
            "summary": "Apple announced record quarterly earnings today.",
            "provider": {"displayName": "Reuters"},
            "canonicalUrl": {"url": "https://example.com/aapl-earnings"},
            "pubDate": "2026-05-25T12:00:00Z",
        }
    }
    result = _extract_article_data(article)
    assert result["title"] == "Apple Reports Record Earnings"
    assert result["summary"] == "Apple announced record quarterly earnings today."
    assert result["publisher"] == "Reuters"
    assert result["link"] == "https://example.com/aapl-earnings"
    assert isinstance(result["pub_date"], datetime)


def test_extract_article_data_flat_structure():
    """Flat dict (no 'content' key) falls back to top-level fields."""
    article = {
        "title": "Market Update",
        "publisher": "Bloomberg",
        "link": "https://example.com/market",
    }
    result = _extract_article_data(article)
    assert result["title"] == "Market Update"
    assert result["publisher"] == "Bloomberg"
    assert result["link"] == "https://example.com/market"
    assert result["pub_date"] is None


def test_extract_article_data_missing_fields():
    """Missing optional fields fall back to defaults without crashing."""
    article = {"content": {}}
    result = _extract_article_data(article)
    assert result["title"] == "No title"
    assert result["summary"] == ""
    assert result["publisher"] == "Unknown"
    assert result["link"] == ""
    assert result["pub_date"] is None


def test_extract_article_data_empty_dict():
    """Empty dict (flat fallback) returns all defaults."""
    result = _extract_article_data({})
    assert result["title"] == "No title"
    assert result["publisher"] == "Unknown"
    assert result["link"] == ""


# ---------------------------------------------------------------------------
# get_news_yfinance — real API call
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_news_yfinance_real():
    """Real yfinance news for AAPL returns well-formed string."""
    data = get_news_yfinance(TICKER, START_DATE, END_DATE)

    # Must be a string (not a crash/None)
    assert isinstance(data, str)
    assert len(data) > 0

    # If news were found, header is present. If none found, message states that.
    if "No news found" in data:
        # Still a valid response — ticker news sometimes empty for short windows
        assert TICKER in data
    else:
        assert f"## {TICKER}" in data
        assert START_DATE in data
        assert END_DATE in data
        # At least one article rendered with ### title
        assert "### " in data


@pytest.mark.integration
def test_get_news_yfinance_invalid_ticker():
    """Garbage ticker returns error message, not an unhandled exception."""
    data = get_news_yfinance("ZZZZZ-INVALID", START_DATE, END_DATE)
    assert isinstance(data, str)
    # yfinance may succeed on unknown tickers (no-op), or return error. Both are OK.
    assert len(data) > 0


# ---------------------------------------------------------------------------
# get_global_news_yfinance — real API call (slower)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_get_global_news_yfinance_real():
    """Global/macro news returns well-formed string."""
    data = get_global_news_yfinance(END_DATE, look_back_days=3, limit=2)

    assert isinstance(data, str)
    assert len(data) > 0

    if "No global news found" in data:
        # Valid-but-empty response
        assert END_DATE in data
    else:
        assert "Global Market News" in data
        # At least one article rendered
        assert "### " in data
