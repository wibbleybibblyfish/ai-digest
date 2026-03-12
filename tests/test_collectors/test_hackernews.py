import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from ai_digest.collectors.hackernews import HackerNewsCollector


@pytest.fixture
def hn_config():
    return {"enabled": True, "keywords": ["AI", "Claude", "LLM"], "min_points": 20}


@pytest.fixture
def mock_hn_response():
    return {"hits": [
        {"title": "Claude Code is amazing", "url": "https://example.com/claude-code", "objectID": "12345",
         "points": 150, "num_comments": 80, "created_at_i": int(datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc).timestamp()), "story_text": "Some description..."},
        {"title": "New LLM benchmark", "url": "https://example.com/benchmark", "objectID": "12346",
         "points": 50, "num_comments": 20, "created_at_i": int(datetime(2026, 3, 12, 7, 0, tzinfo=timezone.utc).timestamp()), "story_text": ""},
        {"title": "Low score post", "url": "https://example.com/low", "objectID": "12347",
         "points": 5, "num_comments": 2, "created_at_i": int(datetime(2026, 3, 12, 6, 0, tzinfo=timezone.utc).timestamp()), "story_text": ""},
    ]}


@pytest.mark.asyncio
async def test_hn_collector_filters_by_min_points(hn_config, mock_hn_response):
    collector = HackerNewsCollector(hn_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.hackernews.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = mock_hn_response
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert len(items) == 2  # low score filtered
    assert items[0].source == "hn"


@pytest.mark.asyncio
async def test_hn_collector_normalises_engagement(hn_config, mock_hn_response):
    mock_hn_response["hits"] = mock_hn_response["hits"][:2]
    collector = HackerNewsCollector(hn_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.hackernews.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = mock_hn_response
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert items[0].engagement_score > items[1].engagement_score
    assert 0 <= items[0].engagement_score <= 100
