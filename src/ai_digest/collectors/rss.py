from __future__ import annotations

import calendar
import html as html_lib
import logging
import re
from datetime import datetime, timezone

import feedparser

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem

logger = logging.getLogger(__name__)

RSS_FIXED_SCORE = 50.0

_AI_KEYWORDS = re.compile(
    r'\b(?:AI|artificial intelligence|LLM|Claude|Anthropic|OpenAI|GPT|'
    r'machine learning|deep learning|neural|chatbot|large language model|'
    r'AI agent|generative|Gemini|Copilot|Midjourney|Sora|diffusion)\b',
    re.IGNORECASE,
)


class RSSCollector(BaseCollector):
    def __init__(self, config: dict):
        self.feeds = config.get("feeds", [])
        self.max_items = config.get("max_items_per_run", 8)

    async def collect(self, since: datetime) -> list[RawItem]:
        since_ts = since.timestamp()
        all_items: list[RawItem] = []
        for feed_config in self.feeds:
            try:
                items = self._collect_feed(feed_config, since_ts)
                all_items.extend(items)
            except Exception as e:
                logger.warning(f"Failed to parse feed {feed_config.get('name', '?')}: {e}")
        all_items.sort(key=lambda x: x.timestamp, reverse=True)
        return all_items[:self.max_items]

    def _collect_feed(self, feed_config: dict, since_ts: float) -> list[RawItem]:
        feed = feedparser.parse(feed_config["url"])
        items = []
        for entry in feed.entries:
            published = getattr(entry, "published_parsed", None)
            if not published:
                continue
            entry_ts = calendar.timegm(published)
            if entry_ts < since_ts:
                continue
            if not _AI_KEYWORDS.search(entry.title):
                continue
            title = html_lib.unescape(entry.title)
            snippet = html_lib.unescape(entry.get("summary", ""))[:300]
            items.append(RawItem(
                title=title,
                url=entry.link,
                source="rss",
                engagement_score=RSS_FIXED_SCORE,
                content_snippet=snippet,
                timestamp=datetime.fromtimestamp(entry_ts, tz=timezone.utc),
                metadata={"feed_name": feed_config.get("name", "Unknown")},
            ))
        return items
