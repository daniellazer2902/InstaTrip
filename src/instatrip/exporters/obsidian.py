from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ..models import PostInsight
from ..profiles import get as get_profile


def _frontmatter_value(v: Any) -> str:
    """Sérialise une valeur pour la frontmatter YAML (str safe)."""
    if v is None:
        return ""
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    s = str(v)
    if any(c in s for c in (':', '#', '"', "'", '\n')) or s.startswith(('!', '?', '|', '>')):
        safe = s.replace('"', '\\"')
        return f'"{safe}"'
    return s


def _note(insight: PostInsight, attribute_fields: list[tuple[str, str]]) -> str:
    safe_title = insight.title.replace('"', '\\"')
    fm = [
        "---",
        f"shortcode: {insight.shortcode}",
        f'title: "{safe_title}"',
        f"category: {insight.category}",
    ]
    for key, _label in attribute_fields:
        val = insight.attributes.get(key)
        fm.append(f"{key}: {_frontmatter_value(val) if val else ''}")
    fm.append(f"tags: [{', '.join(insight.tags)}]")
    fm.append(f"url: {insight.url}")
    fm.append("---")
    fm.append("")
    fm.append(f"# {insight.title}")
    fm.append("")
    fm.append(insight.description)
    fm.append("")
    for key, label in attribute_fields:
        val = insight.attributes.get(key)
        if val:
            if key == "city":
                fm.append(f"{label} : [[{val}]]")
            else:
                fm.append(f"{label} : {val}")
    fm.append("")
    fm.append(f"[Voir le post]({insight.url})")
    fm.append("")
    return "\n".join(fm)


def export_obsidian(
    insights: list[PostInsight],
    out_dir: Path,
    collection_slug: str,
    profile_name: str = "voyage",
) -> Path:
    profile = get_profile(profile_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    posts_dir = out_dir / "posts"
    posts_dir.mkdir(parents=True, exist_ok=True)
    for i in insights:
        (posts_dir / f"{i.shortcode}.md").write_text(
            _note(i, profile.attribute_fields), encoding="utf-8"
        )

    base_path = out_dir / f"{collection_slug}.base"
    if not base_path.exists():
        base_path.write_text(profile.base_template, encoding="utf-8")

    # Index avec groupBy sur le 1er champ d'attribut (ville/cuisine/groupe_musculaire)
    primary_key = profile.attribute_fields[0][0] if profile.attribute_fields else None
    grouped: dict[str, list[PostInsight]] = defaultdict(list)
    autres: list[PostInsight] = []
    for i in insights:
        primary = i.attributes.get(primary_key) if primary_key else None
        if primary:
            grouped[str(primary)].append(i)
        else:
            autres.append(i)

    lines = [
        f"# {collection_slug}",
        "",
        f"> Profil : **{profile.name}** — {profile.description}",
        "",
        f"> Vue base interactive (filtres dynamiques) : [[{collection_slug}.base]]",
        "",
        f"![[{collection_slug}.base]]",
        "",
        "---",
        "",
        f"## Index par {profile.attribute_fields[0][1] if primary_key else 'catégorie'} (fallback)",
        "",
    ]
    for key in sorted(grouped.keys()):
        lines.append(f"## {key}")
        for i in grouped[key]:
            badge = ""
            if len(profile.attribute_fields) >= 2:
                sub = i.attributes.get(profile.attribute_fields[1][0])
                if sub:
                    badge = f" ({sub})"
            lines.append(f"- [[{i.shortcode}]] — {i.title}{badge}")
        lines.append("")
    if autres:
        lines.append("## Sans rattachement")
        for i in autres:
            lines.append(f"- [[{i.shortcode}]] — {i.title}")
        lines.append("")
    index = out_dir / f"{collection_slug}.md"
    index.write_text("\n".join(lines), encoding="utf-8")
    return index
