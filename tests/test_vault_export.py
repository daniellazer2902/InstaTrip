from datetime import date

from instatrip.exporters.vault import export_vault
from instatrip.models import PostInsight

REPO = {"full_name": "firecrawl/firecrawl", "url": "https://github.com/firecrawl/firecrawl",
        "description": "Web data for agents", "stars": 200000, "language": "TypeScript",
        "pushed_at": "2026-11-01", "license": "agpl-3.0", "archived": False,
        "confidence": "nom-exact", "query": "firecrawl"}


def _ins(sc, category="repo", title="Titre", repos=None, **attrs):
    return PostInsight(shortcode=sc, url=f"https://www.instagram.com/p/{sc}/", category=category,
                       title=title, description=f"desc {sc}", tags=["scraping"],
                       attributes={"repos": repos or [], **attrs})


def test_one_note_per_repo_across_videos(tmp_path):
    insights = [_ins("A", title="Scraper le web", stack=["python"], cas_usage="Scraper un site"),
                _ins("B", title="Top 5 repos", stack=["mcp"])]
    resolved = {"A": [REPO], "B": [REPO]}
    stats = export_vault(insights, resolved, tmp_path, today=date(2026, 11, 17))
    assert stats == {"repos": 1, "astuces": 0}
    note = (tmp_path / "Repos" / "firecrawl-firecrawl.md").read_text(encoding="utf-8")
    assert 'type: "veille-repo"' in note
    assert 'statut: "a-tester"' in note
    assert "sources: 2" in note
    assert 'stack: ["mcp", "python"]' in note
    assert "https://www.instagram.com/p/A/" in note and "https://www.instagram.com/p/B/" in note
    assert (tmp_path / "Veille-Tech.base").exists() and (tmp_path / "Veille-Tech.md").exists()


def test_update_preserves_user_status_notes_and_old_sources(tmp_path):
    export_vault([_ins("A")], {"A": [REPO]}, tmp_path)
    p = tmp_path / "Repos" / "firecrawl-firecrawl.md"
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace('statut: "a-tester"', 'statut: "adopte"\nperso: "ok"')
    txt += "Testé sur le projet X, top.\n"
    p.write_text(txt, encoding="utf-8")

    export_vault([_ins("C", title="Encore lui")], {"C": [{**REPO, "stars": 210000}]}, tmp_path)
    after = p.read_text(encoding="utf-8")
    assert 'statut: "adopte"' in after and 'statut: "a-tester"' not in after
    assert 'perso: "ok"' in after
    assert "Testé sur le projet X, top." in after
    assert "stars: 210000" in after
    assert "/p/A/" in after and "/p/C/" in after
    assert "sources: 2" in after


def test_post_without_resolved_repo_becomes_astuce(tmp_path):
    insights = [
        _ins("T", category="tip-ia", title="Prompt: plan mode", outils=["Claude Code"]),
        _ins("U", category="repo", title="Repo mystère", repos=["mystere"], mot_cle_cta="REPO"),
        _ins("Z", category="autre", title="Rien"),
    ]
    resolved = {"T": [], "U": [{"query": "mystere", "confidence": "non-resolu"}], "Z": []}
    stats = export_vault(insights, resolved, tmp_path)
    assert stats == {"repos": 0, "astuces": 2}
    files = {p.name for p in (tmp_path / "Astuces").glob("*.md")}
    assert files == {"Prompt plan mode.md", "Repo mystère.md"}
    u = (tmp_path / "Astuces" / "Repo mystère.md").read_text(encoding="utf-8")
    assert 'repos_non_resolus: ["mystere"]' in u
    assert "`REPO`" in u

    # relance : même fichier réutilisé (recherche par shortcode), pas de doublon
    insights[0] = _ins("T", category="tip-ia", title="Titre reformulé")
    export_vault(insights, resolved, tmp_path)
    assert {p.name for p in (tmp_path / "Astuces").glob("*.md")} == files


VEILLE_A = {
    "shortcode": "A",
    "contenu": "1. Clés API dans le .env\n2. RLS activée",
    "liens": [{"url": "https://firecrawl.dev", "label": "Site"}],
    "verdict": "utile", "pertinence": 4,
    "analyse": "Remplace un scraper maison.\nBon pour les agents.",
    "comment_tester": "1. `npx firecrawl`",
    "limites": ["AGPL"], "idees_projets": ["Veille auto"],
    "repos": {"firecrawl/firecrawl": {"resume": "API de scraping.", "fonctionnalites": ["crawl"],
                                      "installation": "docker", "maturite": "actif",
                                      "correspondance_video": "fausse"}},
}


def test_veille_analysis_is_rendered_in_repo_note(tmp_path):
    export_vault([_ins("A")], {"A": [REPO]}, tmp_path, veille={"A": VEILLE_A})
    note = (tmp_path / "Repos" / "firecrawl-firecrawl.md").read_text(encoding="utf-8")
    assert 'verdict: "utile"' in note and "pertinence: 4" in note
    assert "> [!abstract] Verdict : ✅ utile · pertinence 4/5" in note
    assert "> Bon pour les agents." in note
    assert "## Le dépôt" in note and "**Installation** : docker" in note
    assert "[!danger] Le README ne correspond pas" in note
    assert "## Ce que dit la vidéo" in note and "2. RLS activée" in note
    assert "- [Site](https://firecrawl.dev)" in note
    assert "## Comment tester" in note and "- AGPL" in note


def test_veille_content_is_rendered_in_astuce_note(tmp_path):
    v = {**VEILLE_A, "shortcode": "T", "repos": {}}
    export_vault([_ins("T", category="tuto", title="20 trucs SaaS")], {"T": []}, tmp_path, veille={"T": v})
    note = (tmp_path / "Astuces" / "20 trucs SaaS.md").read_text(encoding="utf-8")
    assert "## Contenu" in note and "1. Clés API dans le .env" in note
    assert 'verdict: "utile"' in note
