from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..models import Category, PostInsight


def _note(insight: PostInsight) -> str:
    safe_title = insight.title.replace('"', '\\"')
    fm = [
        "---",
        f"shortcode: {insight.shortcode}",
        f'title: "{safe_title}"',
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


_BASE_TEMPLATE = """\
filters:
  and:
    - 'shortcode != ""'

formulas:
  cat_icon: 'if(category == "lieu", "📍", if(category == "tips", "💡", if(category == "activite", "🎯", "📝")))'
  ig_link: 'if(url, link(url, "↗ IG"), "")'

properties:
  formula.cat_icon:
    displayName: ""
  title:
    displayName: Titre
  category:
    displayName: Catégorie
  city:
    displayName: Ville
  neighborhood:
    displayName: Quartier
  formula.ig_link:
    displayName: Lien

views:
  - type: cards
    name: "🗾 Tout"
    order: [formula.cat_icon, title, city, neighborhood]

  - type: table
    name: "📍 Lieux"
    filters:
      and: ['category == "lieu"']
    groupBy: { property: city, direction: ASC }
    order: [title, neighborhood, formula.ig_link]

  - type: table
    name: "💡 Tips"
    filters:
      and: ['category == "tips"']
    order: [title, city, formula.ig_link]

  - type: table
    name: "🎯 Activités"
    filters:
      and: ['category == "activite"']
    groupBy: { property: city, direction: ASC }
    order: [title, neighborhood, formula.ig_link]

  - type: table
    name: "🗼 Tokyo"
    filters:
      and: ['city == "Tokyo"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "🏯 Osaka"
    filters:
      and: ['city == "Osaka"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "⛩️ Kyoto"
    filters:
      and: ['city == "Kyoto"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "🗺️ Autres villes"
    filters:
      and:
        - 'city != ""'
        - 'city != "Tokyo"'
        - 'city != "Osaka"'
        - 'city != "Kyoto"'
    groupBy: { property: city, direction: ASC }
    order: [formula.cat_icon, title, neighborhood, formula.ig_link]
"""


def export_obsidian(insights: list[PostInsight], out_dir: Path, collection_slug: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in insights:
        (out_dir / f"{i.shortcode}.md").write_text(_note(i), encoding="utf-8")

    base_path = out_dir / f"{collection_slug}.base"
    if not base_path.exists():
        base_path.write_text(_BASE_TEMPLATE, encoding="utf-8")

    by_city: dict[str, list[PostInsight]] = defaultdict(list)
    tips: list[PostInsight] = []
    for i in insights:
        if i.category is Category.TIPS:
            tips.append(i)
        elif i.city:
            by_city[i.city].append(i)
        else:
            by_city["Sans ville"].append(i)

    lines = [
        f"# {collection_slug}",
        "",
        f"> Vue base interactive (filtres dynamiques) : [[{collection_slug}.base]]",
        "",
        f"![[{collection_slug}.base]]",
        "",
        "---",
        "",
        "## Index par ville (fallback)",
        "",
    ]
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
