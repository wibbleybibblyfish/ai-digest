import json
import subprocess
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from ai_digest.curator import Curator
from ai_digest.models import RawItem


@pytest.fixture
def curator_config():
    return {
        "model": "sonnet",
        "max_candidates": 50,
        "max_output_items": 20,
        "scoring_weights": {"usefulness": 0.35, "wow_factor": 0.35, "shareability": 0.30},
    }


def _raw_item(title: str, score: float = 50.0) -> RawItem:
    return RawItem(
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        source="hn",
        engagement_score=score,
        content_snippet=f"About {title}...",
        timestamp=datetime(2026, 3, 12, tzinfo=timezone.utc),
        metadata={},
    )


def _mock_claude_result(items_json: dict) -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(items_json)
    result.stderr = ""
    return result


@pytest.mark.asyncio
async def test_curator_returns_curated_items(curator_config):
    items = [_raw_item("Claude Code Update", 80), _raw_item("AI Demo", 60)]
    claude_output = {"items": [
        {"index": 0, "usefulness": 8, "wow_factor": 6, "shareability": 7, "combined_score": 7.1, "category": "tool", "summary": "New Claude Code features", "share_hook": "Claude Code just got a massive upgrade"},
        {"index": 1, "usefulness": 5, "wow_factor": 9, "shareability": 8, "combined_score": 7.3, "category": "demo", "summary": "Impressive AI demo", "share_hook": "This AI demo is mind-blowing"},
    ]}
    with patch("ai_digest.curator.subprocess.run", return_value=_mock_claude_result(claude_output)):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert len(curated) == 2
    assert curated[0].category == "demo"  # higher combined_score
    assert curated[1].category == "tool"


@pytest.mark.asyncio
async def test_curator_handles_cli_failure(curator_config):
    items = [_raw_item("Test", 80)]
    result = MagicMock()
    result.returncode = 1
    result.stderr = "something broke"
    result.stdout = ""
    with patch("ai_digest.curator.subprocess.run", return_value=result):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert curated is None


@pytest.mark.asyncio
async def test_curator_handles_timeout(curator_config):
    items = [_raw_item("Test", 80)]
    with patch("ai_digest.curator.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 120)):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert curated is None


@pytest.mark.asyncio
async def test_curator_handles_missing_cli(curator_config):
    items = [_raw_item("Test", 80)]
    with patch("ai_digest.curator.subprocess.run", side_effect=FileNotFoundError):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert curated is None


@pytest.mark.asyncio
async def test_curator_limits_candidates(curator_config):
    curator_config["max_candidates"] = 3
    items = [_raw_item(f"Item {i}", score=100 - i) for i in range(10)]
    claude_output = {"items": [
        {"index": 0, "usefulness": 7, "wow_factor": 7, "shareability": 7, "combined_score": 7.0, "category": "news", "summary": "S", "share_hook": "H"},
    ]}
    with patch("ai_digest.curator.subprocess.run", return_value=_mock_claude_result(claude_output)) as mock_run:
        curator = Curator(curator_config)
        await curator.curate(items)
        prompt_arg = mock_run.call_args[0][0][2]  # -p argument
        # The JSON array is the last part of the prompt — extract it
        json_start = prompt_arg.rfind("[")
        items_in_prompt = json.loads(prompt_arg[json_start:])
        assert len(items_in_prompt) == 3


@pytest.mark.asyncio
async def test_curator_respects_max_output_items(curator_config):
    curator_config["max_output_items"] = 1
    items = [_raw_item(f"Item {i}", score=100 - i) for i in range(5)]
    claude_output = {"items": [
        {"index": i, "usefulness": 7, "wow_factor": 7, "shareability": 7, "combined_score": float(7 - i), "category": "news", "summary": f"Summary {i}", "share_hook": f"Hook {i}"}
        for i in range(5)
    ]}
    with patch("ai_digest.curator.subprocess.run", return_value=_mock_claude_result(claude_output)):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert len(curated) == 1


@pytest.mark.asyncio
async def test_curator_sorts_by_combined_score_descending(curator_config):
    items = [_raw_item(f"Item {i}") for i in range(3)]
    claude_output = {"items": [
        {"index": 0, "usefulness": 5, "wow_factor": 5, "shareability": 5, "combined_score": 5.0, "category": "news", "summary": "Low", "share_hook": "H"},
        {"index": 1, "usefulness": 9, "wow_factor": 9, "shareability": 9, "combined_score": 9.0, "category": "release", "summary": "High", "share_hook": "H"},
        {"index": 2, "usefulness": 7, "wow_factor": 7, "shareability": 7, "combined_score": 7.0, "category": "tool", "summary": "Mid", "share_hook": "H"},
    ]}
    with patch("ai_digest.curator.subprocess.run", return_value=_mock_claude_result(claude_output)):
        curator = Curator(curator_config)
        curated = await curator.curate(items)
    assert curated[0].combined_score == 9.0
    assert curated[1].combined_score == 7.0
    assert curated[2].combined_score == 5.0
