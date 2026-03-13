from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import httpx

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
_HN_META_URLS = {"newsguidelines", "newsfaq", "newswelcome", "showhn", "launches"}
_HN_META_TITLES = re.compile(
    r'\b(HN is for|Hacker News guidelines|Show HN rules|Ask HN rules)\b',
    re.IGNORECASE,
)


class HackerNewsCollector(BaseCollector):
    def __init__(self, config: dict):
        self.keywords = config.get("keywords", ["AI", "LLM"])
        self.min_points = config.get("min_points", 20)

    def _is_hn_meta(self, hit: dict) -> bool:
        url = hit.get("url", "")
        if any(slug in url for slug in _HN_META_URLS):
            return True
        if _HN_META_TITLES.search(hit.get("title", "")):
            return True
        return False

    def _title_matches(self, title: str) -> bool:
        title_lower = title.lower()
        for kw in self.keywords:
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', title_lower):
                return True
        return False

    async def collect(self, since: datetime) -> list[RawItem]:
        since_ts = int(since.timestamp())
        seen: dict[str, dict] = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for kw in self.keywords:
                resp = await client.get(ALGOLIA_URL, params={
                    "query": kw,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{since_ts},points>{self.min_points}",
                    "hitsPerPage": 100,
                })
                resp.raise_for_status()
                for h in resp.json().get("hits", []):
                    oid = h.get("objectID")
                    if oid and oid not in seen and self._title_matches(h.get("title", "")) and not self._is_hn_meta(h):
                        seen[oid] = h
        hits = [h for h in seen.values() if h.get("points", 0) > self.min_points]
        if not hits:
            return []
        raw_scores = [h.get("points", 0) + h.get("num_comments", 0) * 1.5 for h in hits]
        return self._normalise_and_build(hits, raw_scores)

    def _normalise_and_build(self, hits: list[dict], raw_scores: list[float]) -> list[RawItem]:
        sorted_scores = sorted(raw_scores)
        items = []
        for hit, score in zip(hits, raw_scores):
            rank = sorted_scores.index(score)
            percentile = (rank / max(len(sorted_scores) - 1, 1)) * 100
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
            raw_text = hit.get("story_text") or ""
            snippet = html.unescape(re.sub(r"<[^>]+>", "", raw_text)).strip()[:300] if raw_text else ""
            items.append(RawItem(
                title=hit.get("title", ""),
                url=url,
                source="hn",
                engagement_score=percentile,
                content_snippet=snippet,
                timestamp=datetime.fromtimestamp(hit.get("created_at_i", 0), tz=timezone.utc),
                metadata={
                    "points": hit.get("points", 0),
                    "num_comments": hit.get("num_comments", 0),
                    "hn_id": hit.get("objectID", ""),
                },
            ))
        return items
