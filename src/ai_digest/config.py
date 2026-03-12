from __future__ import annotations
import os
from copy import deepcopy
from pathlib import Path
import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".ai-digest"

DEFAULT_CONFIG: dict = {
    "reddit": {
        "enabled": False,
        "subreddits": ["artificial", "MachineLearning", "ClaudeAI", "LocalLLaMA", "singularity", "ChatGPT"],
        "min_score": 10,
    },
    "hackernews": {
        "enabled": True,
        "keywords": ["AI", "LLM", "Claude", "Anthropic", "OpenAI", "GPT", "machine learning", "large language model", "AI agent", "Claude Code"],
        "min_points": 20,
    },
    "rss": {
        "enabled": True,
        "max_items_per_run": 8,
        "feeds": [
            {"url": "https://www.anthropic.com/blog/rss", "name": "Anthropic"},
            {"url": "https://openai.com/blog/rss", "name": "OpenAI"},
            {"url": "https://blog.google/technology/ai/rss", "name": "Google AI"},
            {"url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "name": "The Verge"},
        ],
    },
    "claude": {
        "model": "sonnet",
        "max_candidates": 50,
        "max_output_items": 20,
        "scoring_weights": {"usefulness": 0.35, "wow_factor": 0.35, "shareability": 0.30},
    },
    "output": {"open_browser": True, "digest_dir": "~/.ai-digest/digests"},
    "default_lookback_hours": 24,
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict:
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(yaml.dump(DEFAULT_CONFIG, default_flow_style=False, sort_keys=False))
        return deepcopy(DEFAULT_CONFIG)
    with open(config_path) as f:
        user_config = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_CONFIG, user_config)


def validate_env(config: dict) -> list[str]:
    errors = []
    if config.get("reddit", {}).get("enabled"):
        if not os.environ.get("REDDIT_CLIENT_ID"):
            errors.append("REDDIT_CLIENT_ID environment variable is required when reddit is enabled")
        if not os.environ.get("REDDIT_CLIENT_SECRET"):
            errors.append("REDDIT_CLIENT_SECRET environment variable is required when reddit is enabled")
    return errors
