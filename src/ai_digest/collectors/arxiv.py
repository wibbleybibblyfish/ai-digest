from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem

ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

_BOOST_KEYWORDS = re.compile(
    r'\b(?:LLM|Claude|GPT|Anthropic|OpenAI|language model|AI agent|'
    r'transformer|RLHF|fine.?tuning|prompt|reasoning|chain.of.thought)\b',
    re.IGNORECASE,
)

ARXIV_BASE_SCORE = 50.0
ARXIV_BOOST_SCORE = 65.0


class ArxivCollector(BaseCollector):
    def __init__(self, config: dict):
        self.categories = config.get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        self.max_items = config.get("max_items_per_run", 10)

    async def collect(self, since: datetime) -> list[RawItem]:
        cat_query = " OR ".join(f"cat:{c}" for c in self.categories)
        query = f"({cat_query})"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(ARXIV_API_URL, params={
                "search_query": query,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": self.max_items * 2,
            })
            resp.raise_for_status()

        items = self._parse_feed(resp.text, since)
        items.sort(key=lambda x: x.engagement_score, reverse=True)
        return items[:self.max_items]

    def _parse_feed(self, xml_text: str, since: datetime) -> list[RawItem]:
        root = ET.fromstring(xml_text)
        items: list[RawItem] = []
        since_aware = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
        for entry in root.findall(f"{_ATOM_NS}entry"):
            published_el = entry.find(f"{_ATOM_NS}published")
            if published_el is None or published_el.text is None:
                continue
            published = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
            if published < since_aware:
                continue

            title_el = entry.find(f"{_ATOM_NS}title")
            title = (title_el.text or "").strip() if title_el is not None else ""

            link_el = entry.find(f"{_ATOM_NS}link[@rel='alternate']")
            url = link_el.get("href", "") if link_el is not None else ""
            if not url:
                id_el = entry.find(f"{_ATOM_NS}id")
                url = (id_el.text or "").strip() if id_el is not None else ""

            summary_el = entry.find(f"{_ATOM_NS}summary")
            snippet = (summary_el.text or "").strip()[:300] if summary_el is not None else ""

            score = ARXIV_BOOST_SCORE if _BOOST_KEYWORDS.search(title) else ARXIV_BASE_SCORE

            items.append(RawItem(
                title=title,
                url=url,
                source="arxiv",
                engagement_score=score,
                content_snippet=snippet,
                timestamp=published,
                metadata={"arxiv_id": url.split("/")[-1] if url else ""},
            ))
        return items
