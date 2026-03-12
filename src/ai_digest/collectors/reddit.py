from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import praw

from ai_digest.collectors.base import BaseCollector
from ai_digest.models import RawItem


class RedditCollector(BaseCollector):
    def __init__(self, config: dict):
        self.subreddits = config.get("subreddits", [])
        self.min_score = config.get("min_score", 10)

    async def collect(self, since: datetime) -> list[RawItem]:
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
            user_agent="ai-digest/0.1.0",
        )
        since_ts = since.timestamp()
        all_items: list[RawItem] = []
        for subreddit_name in self.subreddits:
            subreddit = reddit.subreddit(subreddit_name)
            submissions = []
            for submission in subreddit.new(limit=100):
                if submission.created_utc < since_ts:
                    break
                if submission.score >= self.min_score:
                    submissions.append(submission)
            if not submissions:
                continue
            raw_scores = [math.log(s.score + 1) * s.upvote_ratio for s in submissions]
            sorted_scores = sorted(raw_scores)
            for submission, score in zip(submissions, raw_scores):
                rank = sorted_scores.index(score)
                percentile = (rank / max(len(sorted_scores) - 1, 1)) * 100
                snippet = (submission.selftext or submission.title)[:300]
                all_items.append(RawItem(
                    title=submission.title,
                    url=submission.url,
                    source="reddit",
                    engagement_score=percentile,
                    content_snippet=snippet,
                    timestamp=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                    metadata={
                        "subreddit": submission.subreddit.display_name,
                        "score": submission.score,
                        "upvote_ratio": submission.upvote_ratio,
                        "permalink": f"https://reddit.com{submission.permalink}",
                    },
                ))
        return all_items
