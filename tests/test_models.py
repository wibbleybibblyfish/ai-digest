from datetime import datetime, timezone
from ai_digest.models import RawItem, CuratedItem


def test_raw_item_creation():
    item = RawItem(
        title="Claude 4 Released",
        url="https://anthropic.com/claude-4",
        source="rss",
        engagement_score=50.0,
        content_snippet="Anthropic releases Claude 4...",
        timestamp=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metadata={"feed_name": "Anthropic"},
    )
    assert item.title == "Claude 4 Released"
    assert item.source == "rss"
    assert item.also_on == []


def test_raw_item_normalised_url():
    item = RawItem(
        title="Test",
        url="https://example.com/post?utm_source=twitter&amp;ref=123#comments",
        source="reddit",
        engagement_score=75.0,
        content_snippet="...",
        timestamp=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metadata={},
    )
    assert item.normalised_url == "https://example.com/post"


def test_curated_item_creation():
    raw = RawItem(
        title="Cool AI Demo",
        url="https://reddit.com/r/artificial/cool",
        source="reddit",
        engagement_score=80.0,
        content_snippet="Amazing demo...",
        timestamp=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metadata={"subreddit": "artificial"},
    )
    curated = CuratedItem(
        raw=raw, usefulness=7, wow_factor=9, shareability=8,
        combined_score=7.95, category="demo",
        summary="An impressive real-time AI demo",
        share_hook="This real-time AI demo is wild",
    )
    assert curated.category == "demo"
    assert curated.combined_score == 7.95
