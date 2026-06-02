import importlib
import json
import os
import time
from email.message import Message
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from tradingagents.dataflows.reddit import (
    _fetch_subreddit,
    fetch_reddit_posts,
)

MOCK_REDDIT_RESPONSE = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "AAPL earnings beat estimates",
                    "score": 42,
                    "num_comments": 15,
                    "created_utc": 1_700_000_000,
                    "selftext": (
                        "Apple reported strong Q1 earnings with revenue "
                        "exceeding expectations."
                    ),
                }
            },
            {
                "data": {
                    "title": "Is AAPL a buy right now?",
                    "score": 28,
                    "num_comments": 7,
                    "created_utc": 1_699_900_000,
                    "selftext": "",
                }
            },
        ]
    }
}

MOCK_EMPTY_RESPONSE = {"data": {"children": []}}


def _mock_urlopen(response_data: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock = MagicMock()
    mock.return_value = mock_resp
    return mock


class TestFetchSubreddit:

    def test_valid_response_returns_parsed_posts(self):
        mock = _mock_urlopen(MOCK_REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            posts = _fetch_subreddit("AAPL", "stocks", limit=5, timeout=10.0)
        assert len(posts) == 2
        assert posts[0]["title"] == "AAPL earnings beat estimates"
        assert posts[1]["title"] == "Is AAPL a buy right now?"
        assert posts[0]["score"] == 42

    def test_empty_response_returns_empty_list(self):
        mock = _mock_urlopen(MOCK_EMPTY_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            posts = _fetch_subreddit("AAPL", "stocks", limit=5, timeout=10.0)
        assert posts == []

    def test_http_error_returns_empty_list(self):
        mock = MagicMock()
        mock.side_effect = HTTPError("url", 429, "Too Many Requests", Message(), None)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            posts = _fetch_subreddit("AAPL", "stocks", limit=5, timeout=10.0)
        assert posts == []

    def test_malformed_json_returns_empty_list(self):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = b"<html>error</html>"
        mock = MagicMock()
        mock.return_value = mock_resp
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            posts = _fetch_subreddit("AAPL", "stocks", limit=5, timeout=10.0)
        assert posts == []

    def test_missing_data_field_returns_empty_list(self):
        mock = _mock_urlopen({"no_data": True})
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            posts = _fetch_subreddit("AAPL", "stocks", limit=5, timeout=10.0)
        assert posts == []


class TestFetchRedditPosts:

    def test_aggregates_posts_from_all_subreddits(self):
        mock = _mock_urlopen(MOCK_REDDIT_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            result = fetch_reddit_posts(
                "AAPL",
                subreddits=["stocks", "investing"],
                inter_request_delay=0.01,
            )
        assert "r/stocks" in result
        assert "r/investing" in result
        assert "AAPL earnings beat estimates" in result
        assert "Is AAPL a buy right now?" in result

    def test_calls_fetch_subreddit_for_each_sub(self):
        mock = _mock_urlopen(MOCK_EMPTY_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock) as urlopen_mock:
            fetch_reddit_posts(
                "AAPL",
                subreddits=["stocks", "investing", "wallstreetbets"],
                limit_per_sub=3,
                timeout=5.0,
                inter_request_delay=0.01,
            )
        assert urlopen_mock.call_count == 3

    def test_empty_response_returns_placeholder(self):
        mock = _mock_urlopen(MOCK_EMPTY_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            result = fetch_reddit_posts(
                "AAPL",
                subreddits=["stocks"],
                inter_request_delay=0.01,
            )
        assert isinstance(result, str)
        assert len(result) > 0
        assert "no Reddit posts found mentioning AAPL" in result
        assert "r/stocks" in result

    def test_graceful_degradation_never_raises(self):
        mock = _mock_urlopen(MOCK_EMPTY_RESPONSE)
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            result = fetch_reddit_posts("AAPL", subreddits=["stocks"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_inter_request_delay_single_gap(self):
        mock = _mock_urlopen(MOCK_REDDIT_RESPONSE)
        start = time.time()
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            fetch_reddit_posts(
                "AAPL",
                subreddits=["s1", "s2"],
                inter_request_delay=0.3,
            )
        elapsed = time.time() - start
        assert elapsed >= 0.25

    def test_inter_request_delay_multiple_gaps(self):
        mock = _mock_urlopen(MOCK_REDDIT_RESPONSE)
        start = time.time()
        with patch("tradingagents.dataflows.reddit.urlopen", mock):
            fetch_reddit_posts(
                "AAPL",
                subreddits=["s1", "s2", "s3"],
                inter_request_delay=0.2,
            )
        elapsed = time.time() - start
        assert elapsed >= 0.35


class TestDefaultSubreddits:

    def test_env_var_overrides_default(self):
        override = {"TRADINGAGENTS_REDDIT_SUBREDDITS": "wallstreetbets,options"}
        with patch.dict(os.environ, override, clear=False):
            importlib.reload(importlib.import_module("tradingagents.dataflows.reddit"))
            from tradingagents.dataflows import reddit as reddit_mod

            assert reddit_mod.DEFAULT_SUBREDDITS == ("wallstreetbets", "options")
            mock = _mock_urlopen(MOCK_EMPTY_RESPONSE)
            with patch("tradingagents.dataflows.reddit.urlopen", mock):
                result = reddit_mod.fetch_reddit_posts("TEST")
            assert "r/wallstreetbets" in result
            assert "r/options" in result

        importlib.reload(importlib.import_module("tradingagents.dataflows.reddit"))

    def test_default_subreddits_is_tuple_of_strings(self):
        from tradingagents.dataflows.reddit import DEFAULT_SUBREDDITS

        assert isinstance(DEFAULT_SUBREDDITS, tuple)
        assert len(DEFAULT_SUBREDDITS) > 0
        assert all(isinstance(s, str) for s in DEFAULT_SUBREDDITS)
