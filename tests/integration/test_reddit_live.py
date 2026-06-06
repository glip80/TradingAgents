"""Reddit integration test with real API calls and file-based caching.

Caches raw ``_fetch_subreddit`` responses per ticker+subreddit pair so
repeated test runs don't hammer Reddit's public JSON endpoint.

Cache location:  ``tests/integration/__cache__/reddit/``
Default TTL:     6 hours (set ``REDDIT_CACHE_TTL`` env var to override, in seconds)
Force refresh:   ``REDDIT_REFRESH_CACHE=1`` (ignores cache and rewrites it)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from tradingagents.dataflows.reddit import _fetch_subreddit, fetch_reddit_posts

CACHE_DIR = Path(__file__).resolve().parent / "__cache__" / "reddit"
_DEFAULT_TTL = 6 * 3600  # 6 hours


def _cache_path(ticker: str, sub: str) -> Path:
    key = hashlib.sha256(f"{ticker.upper()}:{sub}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{key}.json"


def _cache_load(ticker: str, sub: str) -> list | str | None:
    path = _cache_path(ticker, sub)
    if not path.exists():
        return None
    if os.environ.get("REDDIT_REFRESH_CACHE"):
        return None
    ttl = int(os.environ.get("REDDIT_CACHE_TTL", str(_DEFAULT_TTL)))
    if time.time() - path.stat().st_mtime > ttl:
        return None
    return json.loads(path.read_text())


def _cache_save(ticker: str, sub: str, data: list | str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(ticker, sub).write_text(json.dumps(data, indent=2, default=str))


@pytest.mark.integration
class TestLiveFetchSubreddit:
    """Real HTTP call to Reddit's public JSON search endpoint.

    Response is cached on first call; subsequent runs use the cache
    for up to 6 hours (or ``REDDIT_CACHE_TTL`` seconds).
    """

    @pytest.mark.parametrize(
        "ticker,sub",
        [
            ("AAPL", "wallstreetbets"),
            ("TSLA", "stocks"),
        ],
    )
    def test_fetch_known_ticker_returns_posts(self, ticker: str, sub: str) -> None:
        posts = _cache_load(ticker, sub)
        if posts is None:
            posts = _fetch_subreddit(ticker, sub, limit=3, timeout=15.0)
            _cache_save(ticker, sub, posts)

        assert isinstance(posts, list), f"Expected list, got {type(posts)}"
        if posts:
            post = posts[0]
            assert "title" in post, "Missing 'title'"
            assert "score" in post, "Missing 'score'"
            assert "num_comments" in post, "Missing 'num_comments'"
            assert "created_utc" in post, "Missing 'created_utc'"
            assert isinstance(post["title"], str) and len(post["title"]) > 0
            assert isinstance(post["score"], int)
            assert isinstance(post["num_comments"], int)

    def test_fetch_unknown_ticker_returns_empty(self) -> None:
        """A gibberish ticker should return an empty list (not crash)."""
        ticker, sub = "ZZZZXXXX", "wallstreetbets"
        posts = _cache_load(ticker, sub)
        if posts is None:
            posts = _fetch_subreddit(ticker, sub, limit=3, timeout=10.0)
            _cache_save(ticker, sub, posts)
        assert posts == []


@pytest.mark.integration
class TestLiveFetchRedditPosts:
    """End-to-end test for ``fetch_reddit_posts`` with real data."""

    def test_fetch_aggregates_from_real_subreddits(self) -> None:
        cache_key = "e2e:agg"
        cached = _cache_load(cache_key, cache_key)
        if cached is not None:
            result = cached
        else:
            result = fetch_reddit_posts(
                "AAPL",
                subreddits=["wallstreetbets", "stocks"],
                limit_per_sub=2,
                timeout=15.0,
                inter_request_delay=1.0,
            )
            _cache_save(cache_key, cache_key, result)

        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 0
        # At least one subreddit section should appear in output
        assert any(
            f"r/{sub}" in result for sub in ["wallstreetbets", "stocks"]
        ), f"No subreddit headers found in:\n{result[:500]}"
