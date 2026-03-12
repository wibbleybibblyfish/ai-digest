from datetime import datetime, timezone

from ai_digest.dedup import deduplicate
from ai_digest.models import RawItem


def _item(title: str, url: str, source: str, score: float = 50.0) -> RawItem:
    return RawItem(
        title=title,
        url=url,
        source=source,
        engagement_score=score,
        content_snippet="...",
        timestamp=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metadata={},
    )


def test_exact_url_dedup():
    items = [
        _item("Claude 4 is here", "https://anthropic.com/blog/claude-4", "rss", 50),
        _item("Claude 4 is here!", "https://anthropic.com/blog/claude-4", "hn", 80),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].source == "hn"
    assert "rss" in result[0].also_on


def test_url_dedup_strips_query_params():
    items = [
        _item("Post", "https://example.com/article?utm_source=twitter", "reddit", 70),
        _item("Post", "https://example.com/article?ref=hn", "hn", 60),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].source == "reddit"


def test_fuzzy_title_dedup():
    items = [
        _item("OpenAI releases GPT-5 with major improvements", "https://openai.com/gpt5", "rss", 50),
        _item("OpenAI releases GPT-5 with major improvements to reasoning", "https://reddit.com/r/ai/gpt5", "reddit", 75),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].source == "reddit"
    assert "rss" in result[0].also_on


def test_no_false_dedup_on_different_titles():
    items = [
        _item("Claude Code gets new features", "https://anthropic.com/claude-code", "rss", 50),
        _item("GPT-5 benchmark results", "https://openai.com/gpt5", "hn", 80),
    ]
    result = deduplicate(items)
    assert len(result) == 2


def test_empty_input():
    assert deduplicate([]) == []


def test_single_item_unchanged():
    items = [_item("Solo item", "https://example.com/solo", "rss", 50)]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].title == "Solo item"


def test_also_on_preserves_existing_sources():
    base = _item("Article", "https://example.com/a", "rss", 30)
    base.also_on = ["twitter"]
    items = [
        base,
        _item("Article", "https://example.com/a", "hn", 80),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].source == "hn"
    assert "rss" in result[0].also_on
    assert "twitter" in result[0].also_on


def test_exact_url_winner_has_highest_score():
    items = [
        _item("Title A", "https://example.com/page", "source1", 10),
        _item("Title B", "https://example.com/page", "source2", 90),
        _item("Title C", "https://example.com/page", "source3", 50),
    ]
    result = deduplicate(items)
    assert len(result) == 1
    assert result[0].source == "source2"
    assert "source1" in result[0].also_on
    assert "source3" in result[0].also_on
