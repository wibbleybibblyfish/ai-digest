"""Integration test — full pipeline with mocked externals."""
from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_digest.cli import _run_pipeline
from ai_digest.config import DEFAULT_CONFIG


def _make_config(digest_dir: str) -> dict:
    config = {**DEFAULT_CONFIG}
    config["output"] = {"digest_dir": digest_dir, "open_browser": False}
    config["reddit"] = {**DEFAULT_CONFIG["reddit"], "enabled": False}
    config["rss"] = {**DEFAULT_CONFIG["rss"], "enabled": False}
    return config


def _make_hn_response(count: int = 5) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "hits": [
            {
                "title": f"AI Story {i}",
                "url": f"https://example.com/story-{i}",
                "objectID": str(1000 + i),
                "points": 100 - i * 10,
                "num_comments": 50 - i * 5,
                "created_at_i": int((now - timedelta(hours=i)).timestamp()),
                "story_text": f"Description of AI story {i}",
            }
            for i in range(count)
        ]
    }


def _make_claude_response(count: int = 5) -> dict:
    categories = ["tool", "demo", "release", "news", "tutorial"]
    return {
        "items": [
            {
                "index": i,
                "usefulness": 8 - i,
                "wow_factor": 7 - i,
                "shareability": 7,
                "combined_score": round(7.5 - i * 0.5, 1),
                "category": categories[i % len(categories)],
                "summary": f"Summary of story {i}",
                "share_hook": f"Check out this AI story {i}!",
            }
            for i in range(count)
        ]
    }


def _mock_subprocess_result(claude_response: dict) -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(claude_response)
    result.stderr = ""
    return result


@pytest.mark.asyncio
async def test_full_pipeline_produces_digest():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        digest_dir = config_dir / "digests"
        digest_dir.mkdir()

        config = _make_config(str(digest_dir))
        hn_response = _make_hn_response()
        claude_response = _make_claude_response()

        mock_hn_resp = MagicMock()
        mock_hn_resp.json.return_value = hn_response
        mock_hn_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_hn_resp)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("ai_digest.collectors.hackernews.httpx.AsyncClient", return_value=mock_http_client),
            patch("ai_digest.collectors.rss.feedparser.parse", return_value=MagicMock(entries=[], bozo=False)),
            patch("ai_digest.curator.subprocess.run", return_value=_mock_subprocess_result(claude_response)),
        ):
            await _run_pipeline(
                config=config,
                config_dir=config_dir,
                digest_dir=digest_dir,
                dry_run=False,
                since_hours=24,
            )

        html_files = list(digest_dir.glob("*.html"))
        digest_files = [f for f in html_files if f.name != "index.html"]
        assert len(digest_files) == 1, f"Expected 1 digest file, found {len(digest_files)}"

        content = digest_files[0].read_text()
        assert "AI Story 0" in content
        assert "copy-btn" in content or "Copy for Slack" in content

        assert (digest_dir / "index.html").exists()

        assert not (config_dir / "state.json").exists()


@pytest.mark.asyncio
async def test_full_pipeline_saves_state_without_since_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        digest_dir = config_dir / "digests"
        digest_dir.mkdir()

        config = _make_config(str(digest_dir))
        hn_response = _make_hn_response()
        claude_response = _make_claude_response()

        mock_hn_resp = MagicMock()
        mock_hn_resp.json.return_value = hn_response
        mock_hn_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_hn_resp)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("ai_digest.collectors.hackernews.httpx.AsyncClient", return_value=mock_http_client),
            patch("ai_digest.collectors.rss.feedparser.parse", return_value=MagicMock(entries=[], bozo=False)),
            patch("ai_digest.curator.subprocess.run", return_value=_mock_subprocess_result(claude_response)),
        ):
            await _run_pipeline(
                config=config,
                config_dir=config_dir,
                digest_dir=digest_dir,
                dry_run=False,
                since_hours=None,
            )

        assert (config_dir / "state.json").exists()
        state = json.loads((config_dir / "state.json").read_text())
        assert "last_run" in state


@pytest.mark.asyncio
async def test_full_pipeline_renders_uncurated_on_claude_failure():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        digest_dir = config_dir / "digests"
        digest_dir.mkdir()

        config = _make_config(str(digest_dir))
        hn_response = _make_hn_response()

        mock_hn_resp = MagicMock()
        mock_hn_resp.json.return_value = hn_response
        mock_hn_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_hn_resp)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        failed_result = MagicMock()
        failed_result.returncode = 1
        failed_result.stderr = "CLI error"
        failed_result.stdout = ""

        with (
            patch("ai_digest.collectors.hackernews.httpx.AsyncClient", return_value=mock_http_client),
            patch("ai_digest.collectors.rss.feedparser.parse", return_value=MagicMock(entries=[], bozo=False)),
            patch("ai_digest.curator.subprocess.run", return_value=failed_result),
        ):
            await _run_pipeline(
                config=config,
                config_dir=config_dir,
                digest_dir=digest_dir,
                dry_run=False,
                since_hours=24,
            )

        html_files = list(digest_dir.glob("*.html"))
        digest_files = [f for f in html_files if f.name != "index.html"]
        assert len(digest_files) == 1

        content = digest_files[0].read_text()
        assert "AI Story 0" in content


@pytest.mark.asyncio
async def test_full_pipeline_dry_run_produces_no_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        digest_dir = config_dir / "digests"
        digest_dir.mkdir()

        config = _make_config(str(digest_dir))
        hn_response = _make_hn_response()

        mock_hn_resp = MagicMock()
        mock_hn_resp.json.return_value = hn_response
        mock_hn_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_hn_resp)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("ai_digest.collectors.hackernews.httpx.AsyncClient", return_value=mock_http_client),
            patch("ai_digest.collectors.rss.feedparser.parse", return_value=MagicMock(entries=[], bozo=False)),
        ):
            await _run_pipeline(
                config=config,
                config_dir=config_dir,
                digest_dir=digest_dir,
                dry_run=True,
                since_hours=24,
            )

        html_files = list(digest_dir.glob("*.html"))
        assert len(html_files) == 0, "Dry run should not write any HTML files"
        assert not (config_dir / "state.json").exists()
