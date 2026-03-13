import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from ai_digest.collectors.youtube import YouTubeCollector


@pytest.fixture
def youtube_config():
    return {
        "enabled": True,
        "max_items_per_run": 8,
        "channels": [
            {"name": "Fireship", "id": "UCsBjURrPoezykLs9EqgamOA"},
            {"name": "Two Minute Papers", "id": "UCbfYPyITQ-7l4upoX8nvctg"},
        ],
    }


def _make_feed(entries):
    feed = MagicMock()
    parsed_entries = []
    for e in entries:
        entry = MagicMock()
        entry.title = e["title"]
        entry.link = e["link"]
        entry.published_parsed = e.get("published_parsed")
        entry.get = lambda key, default="", _e=e: _e.get(key, default)
        parsed_entries.append(entry)
    feed.entries = parsed_entries
    return feed


@pytest.mark.asyncio
async def test_youtube_collector_returns_items(youtube_config):
    mock_entries = [
        {
            "title": "Claude Code just changed everything",
            "link": "https://www.youtube.com/watch?v=abc123",
            "summary": "A look at the new Claude Code features",
            "published_parsed": datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc).timetuple(),
        },
        {
            "title": "New AI model breaks benchmarks",
            "link": "https://www.youtube.com/watch?v=def456",
            "summary": "GPT-5 benchmark results",
            "published_parsed": datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc).timetuple(),
        },
    ]
    collector = YouTubeCollector(youtube_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.youtube.feedparser.parse") as mock_parse:
        mock_parse.return_value = _make_feed(mock_entries)
        items = await collector.collect(since)
    assert len(items) == 4  # 2 entries x 2 channels
    assert all(i.source == "youtube" for i in items)


@pytest.mark.asyncio
async def test_youtube_collector_respects_max_items():
    config = {"max_items_per_run": 1, "channels": [{"name": "Test", "id": "test123"}]}
    mock_entries = [
        {
            "title": "AI video one",
            "link": "https://www.youtube.com/watch?v=a",
            "summary": "desc",
            "published_parsed": datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc).timetuple(),
        },
        {
            "title": "AI video two",
            "link": "https://www.youtube.com/watch?v=b",
            "summary": "desc",
            "published_parsed": datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc).timetuple(),
        },
    ]
    collector = YouTubeCollector(config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.youtube.feedparser.parse") as mock_parse:
        mock_parse.return_value = _make_feed(mock_entries)
        items = await collector.collect(since)
    assert len(items) <= 1


@pytest.mark.asyncio
async def test_youtube_collector_filters_old_items():
    config = {"max_items_per_run": 10, "channels": [{"name": "Test", "id": "test123"}]}
    mock_entries = [
        {
            "title": "Recent AI video",
            "link": "https://www.youtube.com/watch?v=new",
            "summary": "desc",
            "published_parsed": datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc).timetuple(),
        },
        {
            "title": "Old AI video",
            "link": "https://www.youtube.com/watch?v=old",
            "summary": "desc",
            "published_parsed": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc).timetuple(),
        },
    ]
    collector = YouTubeCollector(config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.youtube.feedparser.parse") as mock_parse:
        mock_parse.return_value = _make_feed(mock_entries)
        items = await collector.collect(since)
    assert len(items) == 1
    assert "Recent" in items[0].title
