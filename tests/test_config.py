import os
import tempfile
from pathlib import Path
from ai_digest.config import load_config, DEFAULT_CONFIG, validate_env


def test_load_default_config_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=Path(tmpdir))
        assert config["reddit"]["enabled"] is False
        assert "ClaudeAI" in config["reddit"]["subreddits"]
        assert config["claude"]["model"] == "sonnet"
        assert config["default_lookback_hours"] == 24


def test_load_config_creates_file_if_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        load_config(config_dir=config_dir)
        assert (config_dir / "config.yaml").exists()


def test_load_config_merges_user_overrides():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        (config_dir / "config.yaml").write_text(
            "reddit:\n  min_score: 50\ndefault_lookback_hours: 48\n"
        )
        config = load_config(config_dir=config_dir)
        assert config["reddit"]["min_score"] == 50
        assert config["default_lookback_hours"] == 48
        assert config["reddit"]["enabled"] is False
        assert config["hackernews"]["enabled"] is True


def test_validate_env_no_errors_when_reddit_disabled():
    errors = validate_env({"reddit": {"enabled": False}})
    assert errors == []


def test_validate_env_missing_reddit_keys_when_enabled(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    errors = validate_env({"reddit": {"enabled": True}})
    assert any("REDDIT_CLIENT_ID" in e for e in errors)
