from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, urlunparse


@dataclass
class RawItem:
    title: str
    url: str
    source: str
    engagement_score: float
    content_snippet: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    also_on: list[str] = field(default_factory=list)

    @property
    def normalised_url(self) -> str:
        parsed = urlparse(self.url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


@dataclass
class CuratedItem:
    raw: RawItem
    usefulness: int
    wow_factor: int
    shareability: int
    combined_score: float
    category: str
    summary: str
    share_hook: str
