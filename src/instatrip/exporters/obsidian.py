from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..models import Category, PostInsight


def _note(insight: PostInsight) -> str:
    fm = [
        "---",
        f"shortcode: {insight.shortcode}",
        f"category: {insight.category.value}",
        f"city: {insight.city or ''}",
        f"neighborhood: {insight.neighborhood or ''}",
        f"tags: [{', '.join(insight.tags)}]",
        f"url: {insight.url}",
        "---",
        "",
        f"# {insight.title}",
        "",
        insight.description,
        "",
    ]
    if insight.city:
        fm.append(f"Ville : [[{insight.city}]]")
    if insight.neighborhood:
        fm.append(f"Quartier : {insight.neighborhood}")
    if insight.activity:
        fm.append(f"Activité : {insight.activity}")
    fm.append("")
    fm.append(f"[Voir le post]({insight.url})")
    fm.append("")
    return "\n".join(fm)


def export_obsidian(insights: list[PostInsight], out_dir: Path, collection_slug: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in insights:
        (out_dir / f"{i.shortcode}.md").write_text(_note(i), encoding="utf-8")

    by_city: dict[str, list[PostInsight]] = defaultdict(list)
    tips: list[PostInsight] = []
    for i in insights:
        if i.category is Category.TIPS or not i.city:
            tips.append(i) if i.category is Category.TIPS else by_city["Sans ville"].append(i)
        else:
            by_city[i.city].append(i)

    lines = [f"# {collection_slug}", ""]
    for city in sorted(by_city.keys()):
        lines.append(f"## {city}")
        for i in by_city[city]:
            badge = f" ({i.neighborhood})" if i.neighborhood else ""
            lines.append(f"- [[{i.shortcode}]] — {i.title}{badge}")
        lines.append("")
    if tips:
        lines.append("## Tips")
        for i in tips:
            lines.append(f"- [[{i.shortcode}]] — {i.title}")
        lines.append("")
    index = out_dir / f"{collection_slug}.md"
    index.write_text("\n".join(lines), encoding="utf-8")
    return index
