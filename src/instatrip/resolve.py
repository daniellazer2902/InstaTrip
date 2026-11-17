"""Résolution des noms de dépôts extraits (profil tech) en dépôts GitHub réels.

Passe par la CLI `gh` (authentification déjà gérée par l'utilisateur).
Sortie : data/resolved/<shortcode>.json, idempotent comme les autres phases.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

from .models import PostInsight

console = Console()

Runner = Callable[[list[str]], Optional[str]]

SEARCH_FIELDS = "fullName,name,description,stargazersCount,language,pushedAt,license,isArchived,url"
# L'API search GitHub est limitée à 30 requêtes/minute en authentifié.
SEARCH_PAUSE_S = 2.1
# Un homonyme peu étoilé est souvent un fork ou une copie : l'original a pu être renommé.
LOW_STARS = 100

_GH_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)", re.I)
_OWNER_REPO_RE = re.compile(r"^([\w.-]+)/([\w.-]+)$")


def gh_runner(args: list[str]) -> Optional[str]:
    try:
        res = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if res.returncode != 0:
        return None
    return res.stdout


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_candidate(raw: str) -> tuple[Optional[str], str]:
    """Retourne (owner|None, nom) depuis 'owner/nom', une URL GitHub ou un nom seul."""
    s = raw.strip().strip("`'\"<>()[] ")
    m = _GH_URL_RE.search(s)
    if m:
        owner, name = m.group(1), m.group(2)
    else:
        m = _OWNER_REPO_RE.match(s)
        if m:
            owner, name = m.group(1), m.group(2)
        else:
            owner, name = None, s
    name = re.sub(r"\.git$", "", name).rstrip("/")
    return owner, name


def _from_api(data: dict, confidence: str, query: str) -> dict:
    lic = data.get("license") or {}
    return {
        "full_name": data["full_name"],
        "url": data["html_url"],
        "description": data.get("description") or "",
        "stars": data.get("stargazers_count", 0),
        "language": data.get("language"),
        "pushed_at": (data.get("pushed_at") or "")[:10],
        "license": lic.get("spdx_id") if isinstance(lic, dict) else None,
        "archived": bool(data.get("archived")),
        "confidence": confidence,
        "query": query,
    }


def _from_search(item: dict, confidence: str, query: str) -> dict:
    lic = item.get("license") or {}
    return {
        "full_name": item["fullName"],
        "url": item["url"],
        "description": item.get("description") or "",
        "stars": item.get("stargazersCount", 0),
        "language": item.get("language") or None,
        "pushed_at": (item.get("pushedAt") or "")[:10],
        "license": lic.get("key") if isinstance(lic, dict) else None,
        "archived": bool(item.get("isArchived")),
        "confidence": confidence,
        "query": query,
    }


def resolve_candidate(raw: str, runner: Runner = gh_runner, pause: float = SEARCH_PAUSE_S) -> dict:
    """Résout un candidat. confidence :
    - `exact` : owner/nom vérifié via l'API
    - `nom-exact` : recherche, nom identique (à la casse/ponctuation près), le plus étoilé
    - `a-verifier` : recherche sans nom identique, meilleur résultat proposé
    - `non-resolu` : rien trouvé
    """
    owner, name = parse_candidate(raw)
    if owner:
        out = runner(["api", f"repos/{owner}/{name}"])
        if out:
            try:
                return _from_api(json.loads(out), "exact", raw)
            except (json.JSONDecodeError, KeyError):
                pass

    out = runner(["search", "repos", name, "--limit", "10", "--json", SEARCH_FIELDS])
    if pause:
        time.sleep(pause)
    items: list[dict] = []
    if out:
        try:
            items = json.loads(out)
        except json.JSONDecodeError:
            items = []
    if not items:
        return {"query": raw, "confidence": "non-resolu"}

    target = _norm(name)
    same = [i for i in items if _norm(i.get("name", "")) == target]
    if owner:
        same_owner = [i for i in same if i["fullName"].split("/")[0].lower() == owner.lower()]
        same = same_owner or same
    if same:
        best = max(same, key=lambda i: i.get("stargazersCount", 0))
        conf = "nom-exact" if best.get("stargazersCount", 0) >= LOW_STARS else "a-verifier"
        return _from_search(best, conf, raw)
    best = max(items, key=lambda i: i.get("stargazersCount", 0))
    return _from_search(best, "a-verifier", raw)


def resolve_post(
    insight: PostInsight,
    runner: Runner = gh_runner,
    pause: float = SEARCH_PAUSE_S,
    override: Optional[list[str]] = None,
) -> dict:
    cands = override if override is not None else (insight.attributes.get("repos") or [])
    if isinstance(cands, str):
        cands = [cands]
    seen: set[str] = set()
    repos: list[dict] = []
    for c in cands:
        if not c or not str(c).strip():
            continue
        r = resolve_candidate(str(c), runner=runner, pause=pause)
        key = r.get("full_name", "").lower() or f"?{r['query']}"
        if key in seen:
            continue
        seen.add(key)
        repos.append(r)
    return {"shortcode": insight.shortcode, "repos": repos}


def resolve_all(
    enriched_dir: Path,
    resolved_dir: Path,
    force: bool = False,
    runner: Runner = gh_runner,
    pause: float = SEARCH_PAUSE_S,
    overrides_file: Optional[Path] = None,
) -> dict:
    """overrides_file : JSON {shortcode: ["owner/nom", ...]} saisi à la main.
    Il remplace les candidats extraits ; ces posts sont re-résolus à chaque passage."""
    resolved_dir.mkdir(parents=True, exist_ok=True)
    overrides: dict[str, list[str]] = {}
    if overrides_file and overrides_file.exists():
        overrides = json.loads(overrides_file.read_text(encoding="utf-8"))
    stats = {"processed": 0, "skipped": 0, "repos": 0, "unresolved": 0}
    for p in sorted(enriched_dir.glob("*.json")):
        insight = PostInsight.model_validate_json(p.read_text(encoding="utf-8"))
        out = resolved_dir / f"{insight.shortcode}.json"
        override = overrides.get(insight.shortcode)
        if out.exists() and not force and override is None:
            stats["skipped"] += 1
            continue
        result = resolve_post(insight, runner=runner, pause=pause, override=override)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        stats["processed"] += 1
        for r in result["repos"]:
            if r["confidence"] == "non-resolu":
                stats["unresolved"] += 1
            else:
                stats["repos"] += 1
        if result["repos"]:
            names = ", ".join(r.get("full_name", f"?{r['query']}") for r in result["repos"])
            console.print(f"[cyan]{insight.shortcode}[/cyan] → {names}")
    return stats


def load_resolved(resolved_dir: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not resolved_dir.exists():
        return out
    for p in resolved_dir.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        out[data["shortcode"]] = data.get("repos", [])
    return out
