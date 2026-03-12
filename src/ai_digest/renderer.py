from __future__ import annotations

import webbrowser
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ai_digest.models import CuratedItem, RawItem

_CATEGORY_ORDER = ["release", "tool", "demo", "tutorial", "news", "discussion"]
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


class Renderer:
    def __init__(self, digest_dir: Path) -> None:
        self._digest_dir = digest_dir
        self._digest_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )

    def render_digest(
        self,
        items: list[CuratedItem],
        run_time: datetime,
        stats: dict,
        source_status: dict[str, bool],
        open_browser: bool = False,
    ) -> Path:
        filename = run_time.strftime("%Y-%m-%d") + ".html"
        output_path = self._digest_dir / filename

        grouped = self._group_by_category(items)
        item_dicts = {cat: [self._curated_to_dict(i) for i in cat_items] for cat, cat_items in grouped.items()}
        all_items = [d for cat_items in item_dicts.values() for d in cat_items]

        prev_file, next_file = self._get_nav(filename)

        template = self._env.get_template("digest.html.j2")
        html = template.render(
            title=f"AI Digest — {run_time.strftime('%B %d, %Y')}",
            run_time=run_time,
            grouped_items=item_dicts,
            all_items=all_items,
            stats=stats,
            source_status=source_status,
            prev_file=prev_file,
            next_file=next_file,
            uncurated=False,
        )
        output_path.write_text(html, encoding="utf-8")
        self.render_index()

        if open_browser:
            webbrowser.open(output_path.as_uri())

        return output_path

    def render_uncurated(
        self,
        items: list[RawItem],
        run_time: datetime,
        stats: dict,
        source_status: dict[str, bool],
        open_browser: bool = False,
    ) -> Path:
        filename = run_time.strftime("%Y-%m-%d") + ".html"
        output_path = self._digest_dir / filename

        sorted_items = sorted(items, key=lambda x: x.engagement_score, reverse=True)
        raw_dicts = [self._raw_to_dict(item) for item in sorted_items]

        prev_file, next_file = self._get_nav(filename)

        template = self._env.get_template("digest.html.j2")
        html = template.render(
            title=f"AI Digest (Uncurated) — {run_time.strftime('%B %d, %Y')}",
            run_time=run_time,
            grouped_items={"uncurated": raw_dicts},
            all_items=raw_dicts,
            stats=stats,
            source_status=source_status,
            prev_file=prev_file,
            next_file=next_file,
            uncurated=True,
        )
        output_path.write_text(html, encoding="utf-8")
        self.render_index()

        if open_browser:
            webbrowser.open(output_path.as_uri())

        return output_path

    def render_index(self) -> Path:
        digest_files = sorted(
            [f for f in self._digest_dir.glob("*.html") if f.name != "index.html"],
            reverse=True,
        )
        entries = [{"filename": f.name, "label": f.name.replace(".html", "")} for f in digest_files]

        template = self._env.get_template("index.html.j2")
        html = template.render(entries=entries)

        index_path = self._digest_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")
        return index_path

    def _group_by_category(self, items: list[CuratedItem]) -> OrderedDict:
        groups: dict[str, list[CuratedItem]] = {}
        for item in items:
            groups.setdefault(item.category, []).append(item)

        ordered: OrderedDict = OrderedDict()
        for cat in _CATEGORY_ORDER:
            if cat in groups:
                ordered[cat] = groups[cat]
        for cat, cat_items in groups.items():
            if cat not in ordered:
                ordered[cat] = cat_items

        return ordered

    def _get_nav(self, current_filename: str) -> tuple[str | None, str | None]:
        digest_files = sorted(
            [f.name for f in self._digest_dir.glob("*.html") if f.name != "index.html"]
        )
        if current_filename not in digest_files:
            digest_files.append(current_filename)
            digest_files.sort()

        idx = digest_files.index(current_filename)
        prev_file = digest_files[idx - 1] if idx > 0 else None
        next_file = digest_files[idx + 1] if idx < len(digest_files) - 1 else None
        return prev_file, next_file

    def _curated_to_dict(self, item: CuratedItem) -> dict:
        return {
            "title": item.raw.title,
            "url": item.raw.url,
            "source": item.raw.source,
            "also_on": item.raw.also_on,
            "category": item.category,
            "summary": item.summary,
            "share_hook": item.share_hook,
            "combined_score": item.combined_score,
            "usefulness": item.usefulness,
            "wow_factor": item.wow_factor,
            "shareability": item.shareability,
            "timestamp": item.raw.timestamp,
        }

    def _raw_to_dict(self, item: RawItem) -> dict:
        snippet = item.content_snippet if item.content_snippet != item.title else ""
        return {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "also_on": item.also_on,
            "category": "uncurated",
            "summary": snippet,
            "share_hook": "",
            "combined_score": item.engagement_score,
            "usefulness": None,
            "wow_factor": None,
            "shareability": None,
            "timestamp": item.timestamp,
        }
