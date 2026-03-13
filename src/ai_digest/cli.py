from __future__ import annotations

import asyncio
import logging
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import click

from ai_digest.collectors.arxiv import ArxivCollector
from ai_digest.collectors.github import GitHubTrendingCollector
from ai_digest.collectors.hackernews import HackerNewsCollector
from ai_digest.collectors.reddit import RedditCollector
from ai_digest.collectors.rss import RSSCollector
from ai_digest.collectors.youtube import YouTubeCollector
from ai_digest.config import DEFAULT_CONFIG_DIR, load_config, validate_env
from ai_digest.curator import Curator
from ai_digest.dedup import deduplicate
from ai_digest.models import RawItem
from ai_digest.renderer import Renderer
from ai_digest.state import load_last_run, save_last_run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_since(value: str) -> float:
    value = value.strip().lower()
    if value.endswith("d"):
        return float(value[:-1]) * 24
    if value.endswith("h"):
        return float(value[:-1])
    return float(value)


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be fetched without calling Claude")
@click.option("--since", default=None, help="Override lookback window (e.g. 48h, 2d)")
@click.option("--sources", is_flag=True, help="List configured sources")
@click.option("--index", is_flag=True, help="Open the archive index in browser")
@click.option("--config-dir", default=None, help="Override config directory")
def main(dry_run: bool, since: str | None, sources: bool, index: bool, config_dir: str | None) -> None:
    config_path = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    config = load_config(config_path)

    if sources:
        _show_sources(config)
        return

    digest_dir = Path(config["output"]["digest_dir"]).expanduser()

    if index:
        index_file = digest_dir / "index.html"
        if not index_file.exists():
            renderer = Renderer(digest_dir)
            renderer.render_index()
        webbrowser.open(index_file.as_uri())
        return

    if not dry_run:
        errors = validate_env(config)
        if errors:
            for err in errors:
                click.echo(f"Error: {err}", err=True)
            sys.exit(1)

    since_hours: float | None = None
    if since is not None:
        try:
            since_hours = _parse_since(since)
        except ValueError:
            click.echo(f"Error: invalid --since value '{since}'. Use formats like 48h or 2d.", err=True)
            sys.exit(1)

    asyncio.run(
        _run_pipeline(
            config=config,
            config_dir=config_path,
            digest_dir=digest_dir,
            dry_run=dry_run,
            since_hours=since_hours,
        )
    )


async def _run_pipeline(
    config: dict,
    config_dir: Path,
    digest_dir: Path,
    dry_run: bool,
    since_hours: float | None,
) -> None:
    run_time = datetime.now(timezone.utc)
    since_dt = load_last_run(
        config_dir,
        default_lookback_hours=config.get("default_lookback_hours", 24),
        since_override_hours=since_hours,
    )

    collectors: list[tuple[str, object]] = []
    if config.get("hackernews", {}).get("enabled"):
        collectors.append(("hn", HackerNewsCollector(config["hackernews"])))
    if config.get("reddit", {}).get("enabled"):
        collectors.append(("reddit", RedditCollector(config["reddit"])))
    if config.get("rss", {}).get("enabled"):
        collectors.append(("rss", RSSCollector(config["rss"])))
    if config.get("arxiv", {}).get("enabled"):
        collectors.append(("arxiv", ArxivCollector(config["arxiv"])))
    if config.get("github", {}).get("enabled"):
        collectors.append(("github", GitHubTrendingCollector(config["github"])))
    if config.get("youtube", {}).get("enabled"):
        collectors.append(("youtube", YouTubeCollector(config["youtube"])))

    all_items: list[RawItem] = []
    source_status: dict[str, bool] = {}

    for name, collector in collectors:
        try:
            items = await collector.safe_collect(since_dt)
            source_status[name] = True
            all_items.extend(items)
        except Exception:
            source_status[name] = False
            logger.warning("Collector %s failed", name)

    deduped = deduplicate(all_items)

    if dry_run:
        top = sorted(deduped, key=lambda x: x.engagement_score, reverse=True)[:20]
        click.echo(f"Dry run — {len(deduped)} items after dedup (showing top {len(top)}):")
        for i, item in enumerate(top, 1):
            click.echo(f"  {i:2}. [{item.source:6}] {item.engagement_score:5.1f}  {item.title}")
        return

    stats = {
        "items_scanned": len(all_items),
        "sources": len(collectors),
        "duplicates_removed": len(all_items) - len(deduped),
        "duration_s": (datetime.now(timezone.utc) - run_time).total_seconds(),
    }

    renderer = Renderer(digest_dir)
    curator = Curator(config["claude"])
    click.echo(f"Curating {len(deduped)} items with Claude...")
    curated = await curator.curate(deduped)

    if curated is None:
        output_path = renderer.render_uncurated(
            items=deduped,
            run_time=run_time,
            stats=stats,
            source_status=source_status,
            open_browser=config.get("output", {}).get("open_browser", True),
        )
    else:
        output_path = renderer.render_digest(
            items=curated,
            run_time=run_time,
            stats=stats,
            source_status=source_status,
            open_browser=config.get("output", {}).get("open_browser", True),
        )

    click.echo(f"Digest written to: {output_path}")

    if since_hours is None:
        save_last_run(config_dir, run_time)


def _show_sources(config: dict) -> None:
    click.echo("Configured sources:\n")

    hn_cfg = config.get("hackernews", {})
    enabled = hn_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  HackerNews ({status})")
    if enabled:
        keywords = hn_cfg.get("keywords", [])
        click.echo(f"    keywords: {', '.join(keywords)}")
        click.echo(f"    min_points: {hn_cfg.get('min_points', 20)}")

    click.echo("")

    reddit_cfg = config.get("reddit", {})
    enabled = reddit_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  Reddit ({status})")
    if enabled:
        subreddits = reddit_cfg.get("subreddits", [])
        click.echo(f"    subreddits: r/{', r/'.join(subreddits)}")
        click.echo(f"    min_score: {reddit_cfg.get('min_score', 10)}")

    click.echo("")

    rss_cfg = config.get("rss", {})
    enabled = rss_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  RSS ({status})")
    if enabled:
        feeds = rss_cfg.get("feeds", [])
        for feed in feeds:
            click.echo(f"    - {feed.get('name', 'unnamed')}: {feed.get('url', '')}")
        click.echo(f"    max_items_per_run: {rss_cfg.get('max_items_per_run', 8)}")

    click.echo("")

    arxiv_cfg = config.get("arxiv", {})
    enabled = arxiv_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  arXiv ({status})")
    if enabled:
        categories = arxiv_cfg.get("categories", [])
        click.echo(f"    categories: {', '.join(categories)}")
        click.echo(f"    max_items_per_run: {arxiv_cfg.get('max_items_per_run', 10)}")

    click.echo("")

    github_cfg = config.get("github", {})
    enabled = github_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  GitHub Trending ({status})")
    if enabled:
        topics = github_cfg.get("topics", [])
        click.echo(f"    topics: {', '.join(topics)}")
        click.echo(f"    min_stars: {github_cfg.get('min_stars', 20)}")

    click.echo("")

    youtube_cfg = config.get("youtube", {})
    enabled = youtube_cfg.get("enabled", False)
    status = "enabled" if enabled else "disabled"
    click.echo(f"  YouTube ({status})")
    if enabled:
        channels = youtube_cfg.get("channels", [])
        for ch in channels:
            click.echo(f"    - {ch.get('name', 'unnamed')}")
        click.echo(f"    max_items_per_run: {youtube_cfg.get('max_items_per_run', 8)}")
