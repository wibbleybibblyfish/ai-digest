from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from ai_digest.cli import main, _parse_since


# --- _parse_since unit tests ---

def test_parse_since_hours():
    assert _parse_since("24h") == 24.0


def test_parse_since_half_hours():
    assert _parse_since("48h") == 48.0


def test_parse_since_days():
    assert _parse_since("2d") == 48.0


def test_parse_since_decimal_days():
    assert _parse_since("1.5d") == 36.0


def test_parse_since_bare_number():
    assert _parse_since("12") == 12.0


def test_parse_since_strips_whitespace():
    assert _parse_since("  6h  ") == 6.0


# --- CLI flag tests ---

def test_cli_sources_command():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["--sources", "--config-dir", tmpdir])
        assert result.exit_code == 0
        assert "reddit" in result.output.lower()
        assert "hackernews" in result.output.lower() or "hn" in result.output.lower()
        assert "rss" in result.output.lower()


def test_cli_sources_shows_subreddits():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["--sources", "--config-dir", tmpdir])
        assert result.exit_code == 0
        assert "artificial" in result.output.lower() or "machinelearning" in result.output.lower()


def test_cli_dry_run():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli._run_pipeline", new_callable=AsyncMock) as mock_pipeline:
                result = runner.invoke(main, ["--dry-run", "--config-dir", tmpdir])
                assert result.exit_code == 0
                mock_pipeline.assert_called_once()


def test_cli_dry_run_passes_flag_to_pipeline():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli._run_pipeline", new_callable=AsyncMock) as mock_pipeline:
                runner.invoke(main, ["--dry-run", "--config-dir", tmpdir])
                _, kwargs = mock_pipeline.call_args
                assert kwargs.get("dry_run") is True


def test_cli_since_parsed_and_passed():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli._run_pipeline", new_callable=AsyncMock) as mock_pipeline:
                runner.invoke(main, ["--since", "48h", "--config-dir", tmpdir])
                _, kwargs = mock_pipeline.call_args
                assert kwargs.get("since_hours") == 48.0


def test_cli_since_not_passed_means_none():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli._run_pipeline", new_callable=AsyncMock) as mock_pipeline:
                runner.invoke(main, ["--config-dir", tmpdir])
                _, kwargs = mock_pipeline.call_args
                assert kwargs.get("since_hours") is None


def test_cli_missing_reddit_env_vars_shows_error():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        (config_dir / "config.yaml").write_text("reddit:\n  enabled: true\n")
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")}
        with patch.dict(os.environ, clean_env, clear=True):
            result = runner.invoke(main, ["--config-dir", tmpdir])
            assert result.exit_code != 0 or "required" in result.output.lower() or "error" in result.output.lower()


def test_cli_index_flag_opens_browser():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pre-create the index file so it exists
        (Path(tmpdir) / "index.html").write_text("<html></html>")
        with patch("webbrowser.open") as mock_open:
            result = runner.invoke(main, ["--index", "--config-dir", tmpdir])
            assert result.exit_code == 0
            mock_open.assert_called_once()


def test_cli_invalid_since_format_shows_error():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            result = runner.invoke(main, ["--since", "notavalue", "--config-dir", tmpdir])
            assert result.exit_code != 0 or "error" in result.output.lower() or "invalid" in result.output.lower()


# --- _run_pipeline integration (mocked collectors + curator + renderer) ---

def test_run_pipeline_calls_save_state_on_normal_run():
    """save_last_run should be called when since_hours is None."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli.HackerNewsCollector") as MockHN, \
                 patch("ai_digest.cli.RedditCollector") as MockReddit, \
                 patch("ai_digest.cli.RSSCollector") as MockRSS, \
                 patch("ai_digest.cli.Curator") as MockCurator, \
                 patch("ai_digest.cli.Renderer") as MockRenderer, \
                 patch("ai_digest.cli.save_last_run") as mock_save:

                mock_collector = AsyncMock()
                mock_collector.safe_collect = AsyncMock(return_value=[])
                MockHN.return_value = mock_collector
                MockReddit.return_value = mock_collector
                MockRSS.return_value = mock_collector

                mock_curate_result = MagicMock()
                MockCurator.return_value.curate = AsyncMock(return_value=[])

                mock_render = MagicMock()
                mock_render.render_digest = MagicMock(return_value=Path(tmpdir) / "out.html")
                mock_render.render_uncurated = MagicMock(return_value=Path(tmpdir) / "out.html")
                MockRenderer.return_value = mock_render

                result = runner.invoke(main, ["--config-dir", tmpdir])
                mock_save.assert_called_once()


def test_run_pipeline_skips_save_state_with_since():
    """save_last_run should NOT be called when --since is used."""
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {
            "REDDIT_CLIENT_ID": "test",
            "REDDIT_CLIENT_SECRET": "test",
        }
        with patch.dict(os.environ, env):
            with patch("ai_digest.cli.HackerNewsCollector") as MockHN, \
                 patch("ai_digest.cli.RedditCollector") as MockReddit, \
                 patch("ai_digest.cli.RSSCollector") as MockRSS, \
                 patch("ai_digest.cli.Curator") as MockCurator, \
                 patch("ai_digest.cli.Renderer") as MockRenderer, \
                 patch("ai_digest.cli.save_last_run") as mock_save:

                mock_collector = AsyncMock()
                mock_collector.safe_collect = AsyncMock(return_value=[])
                MockHN.return_value = mock_collector
                MockReddit.return_value = mock_collector
                MockRSS.return_value = mock_collector

                MockCurator.return_value.curate = AsyncMock(return_value=[])

                mock_render = MagicMock()
                mock_render.render_digest = MagicMock(return_value=Path(tmpdir) / "out.html")
                mock_render.render_uncurated = MagicMock(return_value=Path(tmpdir) / "out.html")
                MockRenderer.return_value = mock_render

                runner.invoke(main, ["--since", "48h", "--config-dir", tmpdir])
                mock_save.assert_not_called()
