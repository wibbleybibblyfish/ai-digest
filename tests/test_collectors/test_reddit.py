import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from ai_digest.collectors.reddit import RedditCollector


@pytest.fixture
def reddit_config():
    return {"enabled": True, "subreddits": ["ClaudeAI", "artificial"], "min_score": 10}


def _make_submission(title, url, score, upvote_ratio, created_utc, subreddit_name, selftext=""):
    sub = MagicMock()
    sub.title = title
    sub.url = url
    sub.score = score
    sub.upvote_ratio = upvote_ratio
    sub.created_utc = created_utc
    sub.selftext = selftext
    sub.permalink = f"/r/{subreddit_name}/comments/abc/test"
    sub.subreddit.display_name = subreddit_name
    return sub


@pytest.mark.asyncio
async def test_reddit_collector_filters_by_min_score():
    config = {"enabled": True, "subreddits": ["ClaudeAI"], "min_score": 10}
    now_ts = datetime.now(timezone.utc).timestamp()
    submissions = [
        _make_submission("Good post", "https://example.com/good", 50, 0.9, now_ts - 3600, "ClaudeAI"),
        _make_submission("Low post", "https://example.com/low", 5, 0.8, now_ts - 3600, "ClaudeAI"),
    ]
    collector = RedditCollector(config)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.reddit.praw.Reddit") as MockReddit:
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        mock_subreddit.new.return_value = submissions
        mock_reddit.subreddit.return_value = mock_subreddit
        MockReddit.return_value = mock_reddit
        items = await collector.collect(since)
    assert len(items) == 1
    assert items[0].title == "Good post"


@pytest.mark.asyncio
async def test_reddit_collector_normalises_per_subreddit():
    config = {"enabled": True, "subreddits": ["artificial"], "min_score": 10}
    now_ts = datetime.now(timezone.utc).timestamp()
    submissions = [
        _make_submission("Top", "https://example.com/1", 500, 0.95, now_ts - 3600, "artificial"),
        _make_submission("Mid", "https://example.com/2", 100, 0.85, now_ts - 3600, "artificial"),
        _make_submission("Low", "https://example.com/3", 20, 0.70, now_ts - 3600, "artificial"),
    ]
    collector = RedditCollector(config)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.reddit.praw.Reddit") as MockReddit:
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        mock_subreddit.new.return_value = submissions
        mock_reddit.subreddit.return_value = mock_subreddit
        MockReddit.return_value = mock_reddit
        items = await collector.collect(since)
    assert len(items) == 3
    assert items[0].engagement_score > items[1].engagement_score > items[2].engagement_score
