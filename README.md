# AI Digest

Personal AI news feed. Aggregates from Hacker News and RSS feeds, curates with Claude Code, and renders a ranked HTML digest with copy-for-Slack/WhatsApp buttons.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires [Claude Code](https://claude.ai/code) installed and authenticated for curation. Falls back to uncurated (engagement-ranked) mode if unavailable.

## Usage

```bash
ai-digest              # Run and open digest in browser
ai-digest --dry-run    # Preview without calling Claude
ai-digest --since 48h  # Look back further
ai-digest --since 3d   # Days work too
ai-digest --sources    # Show configured sources
ai-digest --index      # Open archive
```

## Config

Config lives at `~/.ai-digest/config.yaml` (auto-created on first run). Digests saved to `~/.ai-digest/digests/`.

Add RSS/Atom feeds, tweak HN keywords, adjust scoring weights — all in the YAML, no code changes needed.
