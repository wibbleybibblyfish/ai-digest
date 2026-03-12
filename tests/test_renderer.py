from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

import pytest

from ai_digest.renderer import Renderer
from ai_digest.models import RawItem, CuratedItem


def _raw(title: str, source: str = "hn", also_on: list[str] | None = None) -> RawItem:
    return RawItem(
        title=title,
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        source=source,
        engagement_score=80.0,
        content_snippet=f"About {title}",
        timestamp=datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc),
        metadata={},
        also_on=also_on or [],
    )


def _curated(title: str, category: str, score: float, source: str = "hn") -> CuratedItem:
    raw = _raw(title, source, also_on=["reddit"] if source == "hn" else [])
    return CuratedItem(
        raw=raw,
        usefulness=7,
        wow_factor=8,
        shareability=7,
        combined_score=score,
        category=category,
        summary=f"Summary of {title}",
        share_hook=f"Check this out: {title}",
    )


_RUN_TIME = datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc)
_STATS = {"items_scanned": 50, "sources": 3, "duplicates_removed": 5, "duration_s": 12.3}
_SOURCE_STATUS = {"reddit": True, "hn": True, "rss": True}


def test_render_digest_creates_html_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [_curated("AI Tool", "tool", 8.0), _curated("Cool Demo", "demo", 7.5)]
        path = renderer.render_digest(
            items=items,
            run_time=_RUN_TIME,
            stats=_STATS,
            source_status=_SOURCE_STATUS,
        )
        assert path.exists()
        assert path.suffix == ".html"
        content = path.read_text()
        assert "AI Tool" in content
        assert "Cool Demo" in content
        assert "copy-btn" in content or "Copy for Slack" in content


def test_render_digest_filename_format():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [_curated("Test Item", "news", 7.0)]
        path = renderer.render_digest(items=items, run_time=_RUN_TIME, stats=_STATS, source_status=_SOURCE_STATUS)
        assert path.name == "2026-03-12.html"


def test_render_digest_groups_by_category():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [
            _curated("A Release", "release", 9.0),
            _curated("A Tool", "tool", 8.0),
            _curated("A Tutorial", "tutorial", 7.0),
        ]
        path = renderer.render_digest(items=items, run_time=_RUN_TIME, stats=_STATS, source_status=_SOURCE_STATUS)
        content = path.read_text()
        release_pos = content.index("A Release")
        tool_pos = content.index("A Tool")
        tutorial_pos = content.index("A Tutorial")
        # release should appear before tool, tool before tutorial
        assert release_pos < tool_pos < tutorial_pos


def test_render_digest_contains_source_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [_curated("Item", "news", 6.0)]
        path = renderer.render_digest(
            items=items,
            run_time=_RUN_TIME,
            stats=_STATS,
            source_status={"reddit": True, "hn": False, "rss": True},
        )
        content = path.read_text()
        assert "reddit" in content
        assert "hn" in content
        assert "rss" in content


def test_render_digest_shows_also_on():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        raw = _raw("Cross Posted", "hn", also_on=["reddit"])
        item = CuratedItem(
            raw=raw, usefulness=7, wow_factor=7, shareability=7,
            combined_score=7.0, category="news",
            summary="Cross post summary", share_hook="Cross post hook",
        )
        path = renderer.render_digest(items=[item], run_time=_RUN_TIME, stats=_STATS, source_status=_SOURCE_STATUS)
        content = path.read_text()
        assert "reddit" in content.lower()


def test_render_index_creates_index_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_dir = Path(tmpdir)
        (digest_dir / "2026-03-11-090000.html").write_text("<html></html>")
        (digest_dir / "2026-03-12-090000.html").write_text("<html></html>")
        renderer = Renderer(digest_dir)
        index_path = renderer.render_index()
        assert index_path.exists()
        assert index_path.name == "index.html"
        content = index_path.read_text()
        assert "2026-03-12" in content
        assert "2026-03-11" in content


def test_render_index_excludes_index_from_listings():
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_dir = Path(tmpdir)
        (digest_dir / "2026-03-12-090000.html").write_text("<html></html>")
        renderer = Renderer(digest_dir)
        index_path = renderer.render_index()
        content = index_path.read_text()
        # index.html should not link to itself
        assert content.count("index.html") <= 1


def test_render_index_most_recent_first():
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_dir = Path(tmpdir)
        (digest_dir / "2026-03-10-090000.html").write_text("<html></html>")
        (digest_dir / "2026-03-12-090000.html").write_text("<html></html>")
        (digest_dir / "2026-03-11-090000.html").write_text("<html></html>")
        renderer = Renderer(digest_dir)
        index_path = renderer.render_index()
        content = index_path.read_text()
        pos_12 = content.index("2026-03-12")
        pos_11 = content.index("2026-03-11")
        pos_10 = content.index("2026-03-10")
        assert pos_12 < pos_11 < pos_10


def test_render_uncurated_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        raw_items = [
            RawItem(
                title="Uncurated Item",
                url="https://example.com/test",
                source="hn",
                engagement_score=80.0,
                content_snippet="Test content",
                timestamp=datetime(2026, 3, 12, 9, 0, tzinfo=timezone.utc),
                metadata={},
            )
        ]
        path = renderer.render_uncurated(
            items=raw_items,
            run_time=_RUN_TIME,
            stats={"items_scanned": 10, "sources": 1, "duplicates_removed": 0, "duration_s": 5.0},
            source_status={"hn": True, "reddit": False},
        )
        assert path.exists()
        content = path.read_text()
        assert "ncurated" in content  # "Uncurated" or "uncurated"
        assert "Uncurated Item" in content


def test_render_uncurated_shows_failed_source():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        path = renderer.render_uncurated(
            items=[],
            run_time=_RUN_TIME,
            stats={"items_scanned": 0, "sources": 2, "duplicates_removed": 0, "duration_s": 1.0},
            source_status={"hn": True, "reddit": False},
        )
        content = path.read_text()
        assert "reddit" in content.lower()


def test_render_digest_also_regenerates_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [_curated("Item", "news", 7.0)]
        renderer.render_digest(items=items, run_time=_RUN_TIME, stats=_STATS, source_status=_SOURCE_STATUS)
        index = Path(tmpdir) / "index.html"
        assert index.exists()


def test_render_digest_stats_in_footer():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        items = [_curated("Item", "tool", 7.0)]
        path = renderer.render_digest(items=items, run_time=_RUN_TIME, stats=_STATS, source_status=_SOURCE_STATUS)
        content = path.read_text()
        assert "50" in content  # items_scanned


def test_get_nav_returns_none_for_single_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        prev_f, next_f = renderer._get_nav("2026-03-12-090000.html")
        assert prev_f is None
        assert next_f is None


def test_get_nav_returns_prev_next():
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_dir = Path(tmpdir)
        for name in ["2026-03-10-090000.html", "2026-03-11-090000.html", "2026-03-12-090000.html"]:
            (digest_dir / name).write_text("<html></html>")
        renderer = Renderer(digest_dir)
        prev_f, next_f = renderer._get_nav("2026-03-11-090000.html")
        assert prev_f == "2026-03-10-090000.html"
        assert next_f == "2026-03-12-090000.html"


def test_category_order_in_grouped_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        renderer = Renderer(Path(tmpdir))
        from collections import OrderedDict

        items = [
            _curated("Disc", "discussion", 6.0),
            _curated("News", "news", 7.0),
            _curated("Rel", "release", 9.0),
        ]
        grouped = renderer._group_by_category(items)
        assert isinstance(grouped, OrderedDict)
        keys = list(grouped.keys())
        # release appears before news, news before discussion
        assert keys.index("release") < keys.index("news") < keys.index("discussion")
