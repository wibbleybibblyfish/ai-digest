import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from ai_digest.collectors.arxiv import ArxivCollector


@pytest.fixture
def arxiv_config():
    return {"enabled": True, "categories": ["cs.AI", "cs.CL"], "max_items_per_run": 10}


MOCK_ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>A New Approach to LLM Reasoning</title>
    <id>http://arxiv.org/abs/2603.12345v1</id>
    <link href="http://arxiv.org/abs/2603.12345v1" rel="alternate" type="text/html"/>
    <summary>We present a novel method for improving large language model reasoning capabilities using chain-of-thought prompting with verification steps.</summary>
    <published>2026-03-12T18:00:00Z</published>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI"/>
  </entry>
  <entry>
    <title>Quantum Computing Survey</title>
    <id>http://arxiv.org/abs/2603.99999v1</id>
    <link href="http://arxiv.org/abs/2603.99999v1" rel="alternate" type="text/html"/>
    <summary>A comprehensive survey of quantum computing architectures.</summary>
    <published>2026-03-12T12:00:00Z</published>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="cs.AI"/>
  </entry>
</feed>"""


@pytest.mark.asyncio
async def test_arxiv_collector_returns_items(arxiv_config):
    collector = ArxivCollector(arxiv_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.arxiv.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = MOCK_ATOM_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert len(items) == 2
    assert items[0].source == "arxiv"
    assert "LLM" in items[0].title


@pytest.mark.asyncio
async def test_arxiv_collector_boosts_keyword_matches(arxiv_config):
    collector = ArxivCollector(arxiv_config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.arxiv.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = MOCK_ATOM_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    llm_item = [i for i in items if "LLM" in i.title][0]
    quantum_item = [i for i in items if "Quantum" in i.title][0]
    assert llm_item.engagement_score > quantum_item.engagement_score


@pytest.mark.asyncio
async def test_arxiv_collector_respects_max_items():
    config = {"categories": ["cs.AI"], "max_items_per_run": 1}
    collector = ArxivCollector(config)
    since = datetime(2026, 3, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    with patch("ai_digest.collectors.arxiv.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = MOCK_ATOM_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client
        items = await collector.collect(since)
    assert len(items) <= 1
