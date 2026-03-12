from __future__ import annotations

from difflib import SequenceMatcher

from ai_digest.models import RawItem

FUZZY_THRESHOLD = 0.7


def deduplicate(items: list[RawItem]) -> list[RawItem]:
    if not items:
        return []

    url_groups: dict[str, list[RawItem]] = {}
    for item in items:
        url_groups.setdefault(item.normalised_url, []).append(item)

    merged = [_merge_group(group) for group in url_groups.values()]

    final: list[RawItem] = []
    used: set[int] = set()

    for i, item_a in enumerate(merged):
        if i in used:
            continue
        group = [item_a]
        for j, item_b in enumerate(merged):
            if j <= i or j in used:
                continue
            ratio = SequenceMatcher(None, item_a.title.lower(), item_b.title.lower()).ratio()
            if ratio >= FUZZY_THRESHOLD:
                group.append(item_b)
                used.add(j)
        final.append(_merge_group(group))

    return final


def _merge_group(group: list[RawItem]) -> RawItem:
    if len(group) == 1:
        return group[0]

    best = max(group, key=lambda x: x.engagement_score)
    other_sources: list[str] = []

    for item in group:
        if item.source != best.source:
            other_sources.append(item.source)
        other_sources.extend(item.also_on)

    best.also_on = list(set(other_sources))
    return best
