from __future__ import annotations

import calendar
import html as html_lib
import logging
from datetime import datetime, timezone

import feedparser

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem

logger = logging.getLogger(__name__)

YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_FIXED_SCORE = 55.0


class YouTubeCollector(BaseCollector):
    def __init__(self, config: dict):
        self.channels = config.get("channels", [])
        self.max_items = config.get("max_items_per_run", 8)

    async def collect(self, since: datetime) -> list[RawItem]:
        since_ts = since.timestamp()
        all_items: list[RawItem] = []
        for channel in self.channels:
            try:
                items = self._collect_channel(channel, since_ts)
                all_items.extend(items)
            except Exception as e:
                logger.warning(f"Failed to parse YouTube channel {channel.get('name', '?')}: {e}")
        all_items.sort(key=lambda x: x.timestamp, reverse=True)
        return all_items[:self.max_items]

    def _collect_channel(self, channel: dict, since_ts: float) -> list[RawItem]:
        url = f"{YOUTUBE_FEED_URL}?channel_id={channel['id']}"
        feed = feedparser.parse(url)
        items: list[RawItem] = []
        for entry in feed.entries:
            published = getattr(entry, "published_parsed", None)
            if not published:
                continue
            entry_ts = calendar.timegm(published)
            if entry_ts < since_ts:
                continue
            title = html_lib.unescape(entry.title)
            snippet = html_lib.unescape(entry.get("summary", ""))[:300]
            items.append(RawItem(
                title=title,
                url=entry.link,
                source="youtube",
                engagement_score=YOUTUBE_FIXED_SCORE,
                content_snippet=snippet,
                timestamp=datetime.fromtimestamp(entry_ts, tz=timezone.utc),
                metadata={
                    "channel_name": channel.get("name", "Unknown"),
                    "channel_id": channel.get("id", ""),
                },
            ))
        return items
