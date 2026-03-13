from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubTrendingCollector(BaseCollector):
    def __init__(self, config: dict):
        self.keywords = config.get("keywords", ["AI", "LLM", "GPT", "machine-learning", "langchain", "generative-ai"])
        self.min_stars = config.get("min_stars", 20)

    async def collect(self, since: datetime) -> list[RawItem]:
        since_str = since.strftime("%Y-%m-%d")
        keyword_query = " OR ".join(self.keywords)
        query = f"({keyword_query}) pushed:>={since_str} stars:>={self.min_stars}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(GITHUB_SEARCH_URL, params={
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": 50,
            }, headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()

        repos = resp.json().get("items", [])
        repos = [r for r in repos if r.get("stargazers_count", 0) >= self.min_stars]
        if not repos:
            return []

        raw_scores = [r.get("stargazers_count", 0) + r.get("forks_count", 0) * 2 for r in repos]
        return self._normalise_and_build(repos, raw_scores)

    def _normalise_and_build(self, repos: list[dict], raw_scores: list[float]) -> list[RawItem]:
        sorted_scores = sorted(raw_scores)
        items: list[RawItem] = []
        for repo, score in zip(repos, raw_scores):
            rank = sorted_scores.index(score)
            percentile = (rank / max(len(sorted_scores) - 1, 1)) * 100

            pushed_at = repo.get("pushed_at", "")
            try:
                timestamp = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

            items.append(RawItem(
                title=repo.get("full_name", ""),
                url=repo.get("html_url", ""),
                source="github",
                engagement_score=percentile,
                content_snippet=(repo.get("description") or "")[:300],
                timestamp=timestamp,
                metadata={
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language", ""),
                },
            ))
        return items
