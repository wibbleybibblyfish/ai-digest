from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def load_last_run(state_dir: Path, default_lookback_hours: int = 24, since_override_hours: float | None = None) -> datetime:
    if since_override_hours is not None:
        return datetime.now(timezone.utc) - timedelta(hours=since_override_hours)
    state_file = state_dir / "state.json"
    if not state_file.exists():
        return datetime.now(timezone.utc) - timedelta(hours=default_lookback_hours)
    with open(state_file) as f:
        data = json.load(f)
    return datetime.fromisoformat(data["last_run"])


def save_last_run(state_dir: Path, timestamp: datetime) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    with open(state_file, "w") as f:
        json.dump({"last_run": timestamp.isoformat()}, f)
