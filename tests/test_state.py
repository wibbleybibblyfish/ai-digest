import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ai_digest.state import load_last_run, save_last_run


def test_load_last_run_no_file_returns_default_lookback():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = load_last_run(Path(tmpdir), default_lookback_hours=24)
        expected_min = datetime.now(timezone.utc) - timedelta(hours=24, minutes=1)
        expected_max = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59)
        assert expected_min <= result <= expected_max


def test_save_and_load_last_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        now = datetime(2026, 3, 12, 9, 0, 0, tzinfo=timezone.utc)
        save_last_run(state_dir, now)
        state_file = state_dir / "state.json"
        assert state_file.exists()
        loaded = load_last_run(state_dir, default_lookback_hours=24)
        assert loaded == now


def test_load_last_run_with_since_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir)
        old_run = datetime(2026, 3, 11, 9, 0, 0, tzinfo=timezone.utc)
        save_last_run(state_dir, old_run)
        result = load_last_run(state_dir, default_lookback_hours=24, since_override_hours=48)
        expected_min = datetime.now(timezone.utc) - timedelta(hours=48, minutes=1)
        expected_max = datetime.now(timezone.utc) - timedelta(hours=47, minutes=59)
        assert expected_min <= result <= expected_max
