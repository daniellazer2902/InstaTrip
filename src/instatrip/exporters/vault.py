"""Export du profil tech vers le vault Obsidian : une note par ressource.

- Repos/<owner>-<nom>.md : un dépôt GitHub résolu, toutes vidéos confondues
- Astuces/<titre>.md : un post sans dépôt résolu (outil, tip IA, prompt, tuto)

Une note existante est mise à jour sans perdre ce que l'utilisateur y a mis :
les clés de frontmatter non gérées (dont `statut`) et tout le texte hors du
bloc `veille:auto` sont conservés. Les sources déjà listées sont fusionnées.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from ..models import PostInsight

AUTO_START = "<!-- veille:auto:start -->"
AUTO_END = "<!-- veille:auto:end -->"
SKIP_CATEGORIES = {"autre"}
RESOLVED_OK = {"exact", "nom-exact", "a-verifier"}

REPO_KEYS = [
    "type", "repo", "url", "description", "stars", "langage", "dernier_push",
    "licence", "archive", "confiance", "stack", "outils", "tags", "sources", "maj",
]
ASTUCE_KEYS = [
    "type", "shortcode", "categorie", "outils", "stack", "repos_non_resolus",
    "mot_cle_cta", "tags", "url", "maj",
]
_SOURCE_LINE_RE = re.compile(r"^- .*\((https://www\.instagram\.com/[^)]+)\)")


@dataclass
class Source:
    title: str
    url: str
    description: str
    cas_usage: Optional[str] = None

    def line(self) -> str:
        extra = f" : {self.cas_usage}" if self.cas_usage else ""
        return f"- [{self.title}]({self.url}){extra}"


@dataclass
class RepoResource:
    repo: dict
    sources: list[Source] = field(default_factory=list)
    stack: set[str] = field(default_factory=set)
    outils: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)


def _yaml(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple, set)):
        return "[" + ", ".join(json.dumps(str(x), ensure_ascii=False) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)


def _as_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x) for x in v if x]


def safe_filename(s: str, max_len: int = 90) -> str:
    s = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:max_len].rstrip(" .") or "sans-titre"


def _split_note(text: str) -> tuple[list[str], str]:
    """Retourne (lignes de frontmatter, corps)."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[4:end].split("\n"), text[end + 5:]
    return [], text


def _user_frontmatter(lines: list[str], managed: list[str]) -> list[str]:
    """Garde les blocs de frontmatter dont la clé n'est pas gérée par l'export."""
    kept: list[str] = []
    keep = False
    for ln in lines:
        m = re.match(r"^([A-Za-z0-9_-]+):", ln)
        if m:
            keep = m.group(1) not in managed
        if keep:
            kept.append(ln)
    return kept


def _existing_sources(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if AUTO_START in body and AUTO_END in body:
        block = body.split(AUTO_START, 1)[1].split(AUTO_END, 1)[0]
        for ln in block.splitlines():
            m = _SOURCE_LINE_RE.match(ln)
            if m:
                out[m.group(1)] = ln
    return out


def _write_note(
    path: Path,
    managed_fm: list[tuple[str, Any]],
    title: str,
    auto_block: str,
    default_fm: list[tuple[str, Any]],
    default_tail: str,
) -> None:
    managed_keys = [k for k, _ in managed_fm]
    fm_lines = [f"{k}: {_yaml(v)}" for k, v in managed_fm]
    auto = f"{AUTO_START}\n{auto_block.rstrip()}\n{AUTO_END}"
    if path.exists():
        old_fm, old_body = _split_note(path.read_text(encoding="utf-8"))
        fm_lines += _user_frontmatter(old_fm, managed_keys)
        if AUTO_START in old_body and AUTO_END in old_body:
            before = old_body.split(AUTO_START, 1)[0]
            after = old_body.split(AUTO_END, 1)[1]
            body = before + auto + after
        else:
            body = f"# {title}\n\n{auto}\n\n{old_body.lstrip()}"
    else:
        fm_lines += [f"{k}: {_yaml(v)}" for k, v in default_fm]
        body = f"# {title}\n\n{auto}\n\n{default_tail}"
    path.write_text("---\n" + "\n".join(fm_lines) + "\n---\n" + body, encoding="utf-8")


def _repo_note_name(full_name: str) -> str:
    return safe_filename(full_name.replace("/", "-"))


def _collect_repos(
    insights: list[PostInsight], resolved: dict[str, list[dict]]
) -> tuple[dict[str, RepoResource], set[str]]:
    repos: dict[str, RepoResource] = {}
    covered: set[str] = set()
    for i in insights:
        for r in resolved.get(i.shortcode, []):
            if r.get("confidence") not in RESOLVED_OK:
                continue
            key = r["full_name"].lower()
            res = repos.setdefault(key, RepoResource(repo=r))
            if r["confidence"] == "exact" or res.repo.get("confidence") == "a-verifier":
                res.repo = r
            res.sources.append(Source(
                title=i.title, url=str(i.url), description=i.description,
                cas_usage=i.attributes.get("cas_usage"),
            ))
            res.stack.update(_as_list(i.attributes.get("stack")))
            res.outils.update(_as_list(i.attributes.get("outils")))
            res.tags.update(i.tags)
            covered.add(i.shortcode)
    return repos, covered


def _existing_astuce_path(dir_: Path, shortcode: str) -> Optional[Path]:
    needle = f'shortcode: "{shortcode}"'
    for p in dir_.glob("*.md"):
        head = p.read_text(encoding="utf-8")[:600]
        if needle in head:
            return p
    return None


def export_vault(
    insights: list[PostInsight],
    resolved: dict[str, list[dict]],
    vault_dir: Path,
    today: Optional[date] = None,
) -> dict:
    today_s = (today or date.today()).isoformat()
    repos_dir = vault_dir / "Repos"
    astuces_dir = vault_dir / "Astuces"
    repos_dir.mkdir(parents=True, exist_ok=True)
    astuces_dir.mkdir(parents=True, exist_ok=True)

    insights = [i for i in insights if i.category not in SKIP_CATEGORIES]
    repos, covered = _collect_repos(insights, resolved)

    for res in repos.values():
        r = res.repo
        path = repos_dir / f"{_repo_note_name(r['full_name'])}.md"
        prev_sources = _existing_sources(path.read_text(encoding="utf-8")) if path.exists() else {}
        for s in res.sources:
            prev_sources[s.url] = s.line()
        warn = ""
        if r["confidence"] == "a-verifier":
            warn = (f"> [!warning] Correspondance incertaine\n> Nom extrait de la vidéo : "
                    f"`{r['query']}`. Vérifier que c'est bien ce dépôt.\n\n")
        if r.get("archived"):
            warn += "> [!caution] Dépôt archivé\n\n"
        cas = next((s.cas_usage for s in res.sources if s.cas_usage), None)
        auto = (
            f"{warn}> {r.get('description') or '(pas de description)'}\n\n"
            + (f"**Cas d'usage** : {cas}\n\n" if cas else "")
            + f"[{r['full_name']}]({r['url']}) · ⭐ {r.get('stars', 0)}"
            + (f" · {r['language']}" if r.get("language") else "")
            + (f" · dernier push {r['pushed_at']}" if r.get("pushed_at") else "")
            + "\n\n## Vu dans\n\n" + "\n".join(prev_sources.values())
        )
        managed = [
            ("type", "veille-repo"), ("repo", r["full_name"]), ("url", r["url"]),
            ("description", r.get("description") or ""), ("stars", r.get("stars", 0)),
            ("langage", r.get("language")), ("dernier_push", r.get("pushed_at")),
            ("licence", r.get("license")), ("archive", r.get("archived", False)),
            ("confiance", r["confidence"]), ("stack", sorted(res.stack)),
            ("outils", sorted(res.outils)), ("tags", sorted(res.tags | {"veille-tech"})),
            ("sources", len(prev_sources)), ("maj", today_s),
        ]
        _write_note(path, managed, r["full_name"], auto,
                    default_fm=[("statut", "a-tester")],
                    default_tail="## Mes notes\n\n")

    n_astuces = 0
    for i in insights:
        if i.shortcode in covered:
            continue
        unresolved = [r["query"] for r in resolved.get(i.shortcode, [])
                      if r.get("confidence") not in RESOLVED_OK]
        if not unresolved:
            unresolved = [c for c in _as_list(i.attributes.get("repos"))
                          if i.shortcode not in resolved]
        path = _existing_astuce_path(astuces_dir, i.shortcode)
        if path is None:
            path = astuces_dir / f"{safe_filename(i.title)}.md"
            if path.exists():
                path = astuces_dir / f"{safe_filename(i.title)} ({i.shortcode}).md"
        cta = i.attributes.get("mot_cle_cta")
        auto = i.description + "\n\n"
        if i.attributes.get("cas_usage"):
            auto += f"**Cas d'usage** : {i.attributes['cas_usage']}\n\n"
        if unresolved:
            auto += ("> [!question] Dépôt cité mais non identifié\n> "
                     + ", ".join(f"`{u}`" for u in unresolved)
                     + (f"\n> Mot-clé à commenter sur le post : `{cta}`" if cta else "")
                     + "\n\n")
        elif cta:
            auto += f"Mot-clé à commenter sur le post : `{cta}`\n\n"
        auto += f"[Voir le post]({i.url})"
        managed = [
            ("type", "veille-astuce"), ("shortcode", i.shortcode), ("categorie", i.category),
            ("outils", _as_list(i.attributes.get("outils"))),
            ("stack", _as_list(i.attributes.get("stack"))),
            ("repos_non_resolus", unresolved), ("mot_cle_cta", cta),
            ("tags", sorted(set(i.tags) | {"veille-tech"})), ("url", str(i.url)), ("maj", today_s),
        ]
        _write_note(path, managed, i.title, auto,
                    default_fm=[("statut", "a-tester")],
                    default_tail="## Mes notes\n\n")
        n_astuces += 1

    base = vault_dir / "Veille-Tech.base"
    if not base.exists():
        base.write_text(VAULT_BASE, encoding="utf-8")
    index = vault_dir / "Veille-Tech.md"
    if not index.exists():
        index.write_text(VAULT_INDEX, encoding="utf-8")
    return {"repos": len(repos), "astuces": n_astuces}


VAULT_BASE = """\
filters:
  or:
    - 'type == "veille-repo"'
    - 'type == "veille-astuce"'

formulas:
  lien: 'if(url, link(url, "↗"), "")'

properties:
  file.name:
    displayName: Ressource
  statut:
    displayName: Statut
  stars:
    displayName: Étoiles
  stack:
    displayName: Stack
  categorie:
    displayName: Catégorie
  formula.lien:
    displayName: Lien

views:
  - type: table
    name: "Repos à tester"
    filters:
      and:
        - 'type == "veille-repo"'
        - 'statut == "a-tester"'
    order: [file.name, description, stack, stars, dernier_push, formula.lien]
    sort:
      - property: stars
        direction: DESC

  - type: table
    name: "Tous les repos"
    filters:
      and: ['type == "veille-repo"']
    groupBy: { property: statut, direction: ASC }
    order: [file.name, description, stack, stars, confiance, formula.lien]

  - type: table
    name: "Astuces, outils, prompts"
    filters:
      and: ['type == "veille-astuce"']
    groupBy: { property: categorie, direction: ASC }
    order: [file.name, outils, stack, statut, formula.lien]

  - type: table
    name: "Dépôts à identifier"
    filters:
      and:
        - 'type == "veille-astuce"'
        - 'repos_non_resolus.length > 0'
    order: [file.name, repos_non_resolus, mot_cle_cta, formula.lien]
"""

VAULT_INDEX = """\
---
type: index
tags: [veille-tech]
---
# Veille tech

Ressources repérées dans les reels Instagram enregistrés (repos GitHub, outils, astuces IA, prompts).
Alimenté par InstaTrip (profil `tech`), mis à jour à chaque passage sans écraser les notes perso.

Statuts : `a-tester` → `teste` → `adopte` ou `rejete`.

![[Veille-Tech.base]]
"""
