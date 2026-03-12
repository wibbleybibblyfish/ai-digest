from __future__ import annotations

import json
import logging
import subprocess

from ai_digest.models import CuratedItem, RawItem

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an AI news curator. You receive a JSON array of AI-related content items and must score and summarise each one.

For each item, provide:
- usefulness (1-10): How useful is this for a software engineering team?
- wow_factor (1-10): How impressive or surprising is this?
- shareability (1-10): Would this get engagement in a work Slack channel?
- combined_score: Calculate as (usefulness × W1) + (wow_factor × W2) + (shareability × W3)
- category: One of "tool", "demo", "release", "news", "tutorial", "discussion"
- summary: One clear sentence
- share_hook: 1-2 sentence Slack-ready commentary, casual informed tone

Return ONLY valid JSON: {"items": [{"index": N, ...}]}
Score honestly. Most items 4-7. Reserve 8+ for exceptional. Omit items below 4 combined.\
"""

_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "usefulness": {"type": "number"},
                    "wow_factor": {"type": "number"},
                    "shareability": {"type": "number"},
                    "combined_score": {"type": "number"},
                    "category": {"type": "string", "enum": ["tool", "demo", "release", "news", "tutorial", "discussion"]},
                    "summary": {"type": "string"},
                    "share_hook": {"type": "string"},
                },
                "required": ["index", "usefulness", "wow_factor", "shareability", "combined_score", "category", "summary", "share_hook"],
            },
        },
    },
    "required": ["items"],
})


class Curator:
    def __init__(self, config: dict) -> None:
        self._model: str = config.get("model", "sonnet")
        self._max_candidates: int = config["max_candidates"]
        self._max_output_items: int = config["max_output_items"]
        self._weights: dict[str, float] = config["scoring_weights"]

    async def curate(self, items: list[RawItem]) -> list[CuratedItem] | None:
        candidates = sorted(items, key=lambda x: x.engagement_score, reverse=True)[: self._max_candidates]

        weights = self._weights
        system = _SYSTEM_PROMPT.replace("W1", str(weights["usefulness"])).replace("W2", str(weights["wow_factor"])).replace("W3", str(weights["shareability"]))

        user_message = json.dumps(
            [{"index": i, "title": item.title, "snippet": item.content_snippet, "source": item.source, "engagement": item.engagement_score} for i, item in enumerate(candidates)]
        )

        prompt = f"{system}\n\n{user_message}"
        data = self._call_claude(prompt)
        if data is None:
            return None

        return self._build_curated(data, candidates)

    def _call_claude(self, prompt: str) -> dict | None:
        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p", prompt,
                    "--model", self._model,
                    "--output-format", "text",
                    "--no-session-persistence",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.error("Claude CLI failed (exit %d): %s", result.returncode, result.stderr[:500])
                return None

            return self._extract_json(result.stdout)
        except subprocess.TimeoutExpired:
            logger.error("Claude CLI timed out")
            return None
        except FileNotFoundError:
            logger.error("'claude' CLI not found — is Claude Code installed?")
            return None

    def _extract_json(self, text: str) -> dict | None:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fences
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first { to last }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        logger.error("Could not extract JSON from Claude response (first 500 chars): %s", text[:500])
        return None

    def _build_curated(self, data: dict, candidates: list[RawItem]) -> list[CuratedItem]:
        curated: list[CuratedItem] = []

        for entry in data.get("items", []):
            idx = entry.get("index")
            if idx is None or idx >= len(candidates):
                continue
            curated.append(
                CuratedItem(
                    raw=candidates[idx],
                    usefulness=entry["usefulness"],
                    wow_factor=entry["wow_factor"],
                    shareability=entry["shareability"],
                    combined_score=entry["combined_score"],
                    category=entry["category"],
                    summary=entry["summary"],
                    share_hook=entry["share_hook"],
                )
            )

        curated.sort(key=lambda x: x.combined_score, reverse=True)
        return curated[: self._max_output_items]
