import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from ai_digest.collectors.github import GitHubTrendingCollector


@pytest.fixture
def github_config():
    return {"enabled": True, "topics": ["artificial-intelligence", "llm", "machine-learning"], "min_stars": 20}


MOCK_GITHUB_RESPONSE = {
    "items": [
        {
            "full_name": "anthropics/claude-code",
            "html_url": "https://github.com/anthropics/claude-code",
            "description": "Claude Code is an agentic coding tool",
            "stargazers_count": 500,
            "forks_count": 50,
            "language": "TypeScript",
            "topics": ["ai", "llm"],
            "pushed_at": "2026-03-12T10:00:00Z",
            "created_at": "2026-03-01T00:00:00Z",
        },
        {
            "full_name": "user/small-ai-tool",
            "html_url": "https://github.com/user/small-ai-tool",
            "description": "A small AI helper",
            "stargazers_count": 30,
            "forks_count": 5,
            "language": "Python",
            "topics": ["ai"],
            "pushed_at": "2026-03-12T08:00:00Z",
            "created_at": "2026-03-10T00:00:00Z",
        },
        {
            "full_name": "user/tiny-repo",
            "html_url": "https://github.com/user/tiny-repo",
            "description": "Too few stars",
            "stargazers_count": 5,
            "forks_count": 0,
            "language": "Python",
            "topics": ["ai"],
            "pushed_at": "2026-03-12T06:00:00Z",
            "created_at": "2026-03-11T00:00:00Z",
        },
    ]
}


@pytest.mark.asyncio
async def test_github_collector_returns_items(github_config):
    collector = GitHubTrendingCollector(github_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.github.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_GITHUB_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert len(items) == 2
    assert items[0].source == "github"


@pytest.mark.asyncio
async def test_github_collector_normalises_engagement(github_config):
    collector = GitHubTrendingCollector(github_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.github.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_GITHUB_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert items[0].engagement_score > items[1].engagement_score
    assert 0 <= items[0].engagement_score <= 100


@pytest.mark.asyncio
async def test_github_collector_includes_metadata(github_config):
    collector = GitHubTrendingCollector(github_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.github.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_GITHUB_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert "stars" in items[0].metadata
    assert "language" in items[0].metadata
