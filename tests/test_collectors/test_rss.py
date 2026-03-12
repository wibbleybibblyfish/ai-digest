import pytest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from ai_digest.collectors.rss import RSSCollector


@pytest.fixture
def rss_config():
    return {"enabled": True, "max_items_per_run": 8, "feeds": [
        {"url": "https://www.anthropic.com/blog/rss", "name": "Anthropic"},
        {"url": "https://openai.com/blog/rss", "name": "OpenAI"},
    ]}


def _make_feed_entry(title, link, published_ts):
    entry = MagicMock()
    entry.title = title
    entry.link = link
    entry.get.side_effect = lambda key, default="": {"summary": f"Summary of {title}"}.get(key, default)
    entry.published_parsed = time.gmtime(published_ts)
    return entry


@pytest.mark.asyncio
async def test_rss_collector_collects_from_feeds(rss_config):
    # Use single-feed config to avoid mock returning same entries for both feeds
    single_feed_config = {**rss_config, "feeds": [rss_config["feeds"][0]]}
    now_ts = datetime.now(timezone.utc).timestamp()
    entries = [
        _make_feed_entry("Claude Update", "https://anthropic.com/blog/update", now_ts - 3600),
        _make_feed_entry("Old Post", "https://anthropic.com/blog/old", now_ts - 86400 * 3),
    ]
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    collector = RSSCollector(single_feed_config)
    mock_feed = MagicMock()
    mock_feed.entries = entries
    mock_feed.bozo = False
    with patch("ai_digest.collectors.rss.feedparser.parse", return_value=mock_feed):
        items = await collector.collect(since)
    assert len(items) == 1
    assert items[0].title == "Claude Update"
    assert items[0].engagement_score == 50.0


@pytest.mark.asyncio
async def test_rss_collector_caps_at_max_items(rss_config):
    rss_config["max_items_per_run"] = 2
    now_ts = datetime.now(timezone.utc).timestamp()
    entries = [_make_feed_entry(f"Post {i}", f"https://example.com/{i}", now_ts - i * 60) for i in range(5)]
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    collector = RSSCollector(rss_config)
    mock_feed = MagicMock()
    mock_feed.entries = entries
    mock_feed.bozo = False
    with patch("ai_digest.collectors.rss.feedparser.parse", return_value=mock_feed):
        items = await collector.collect(since)
    assert len(items) <= 2
