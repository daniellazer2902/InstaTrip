from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from .auth import login_and_save_state
from .collection import collect_shortcodes
from .config import Settings
from .exporters.excel import export_excel
from .exporters.obsidian import export_obsidian
from .extract import extract_all
from .interpret_runner import run_analysis
from .models import PostInsight

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def auth():
    """Connexion Instagram (1 fois). Sauvegarde la session."""
    s = Settings.load()
    login_and_save_state(s.state_path)


@app.command()
def collect(url: str = typer.Option(None, help="URL de la collection (défaut: env COLLECTION_URL)")):
    """Scrolle la collection et écrit la liste des shortcodes."""
    s = Settings.load()
    target = url or s.collection_url
    if not target:
        raise typer.BadParameter("Fournir --url ou définir COLLECTION_URL dans .env")
    codes = collect_shortcodes(target, s.state_path)
    out = s.project_root / "data" / f"{s.collection_slug}-shortcodes.json"
    out.write_text(json.dumps(codes, indent=2), encoding="utf-8")
    console.print(f"[green]✓ {len(codes)} shortcodes → {out}")


@app.command()
def scrape(
    force: bool = typer.Option(False, help="Force re-download"),
    frame_interval: float = typer.Option(2.0, help="Intervalle (s) entre frames OCR. 1.0 = 2× plus de frames, +50% temps."),
    ocr_confidence: float = typer.Option(0.4, help="Seuil de confiance EasyOCR (0-1). Plus haut = moins de bruit."),
    frame_dedup: bool = typer.Option(True, help="Dédup les frames quasi-identiques (dHash) avant OCR."),
    dedup_threshold: int = typer.Option(6, help="Distance Hamming max pour dédup (0-64). Plus bas = plus strict."),
    dedup_mode: str = typer.Option("bands", help="'bands' (top+bottom 30%, cible overlays texte IG) ou 'full' (image entière)."),
):
    """Phase 1 : extraction brute pour chaque shortcode."""
    s = Settings.load()
    codes_file = s.project_root / "data" / f"{s.collection_slug}-shortcodes.json"
    codes = json.loads(codes_file.read_text(encoding="utf-8"))
    extract_all(
        codes, s, force=force,
        frame_interval=frame_interval,
        ocr_min_confidence=ocr_confidence,
        frame_dedup=frame_dedup,
        dedup_threshold=dedup_threshold,
        dedup_mode=dedup_mode,
    )


@app.command()
def interpret(
    trip_context: str = typer.Option("", help="Contexte (ex: 'Voyage Japon 2026', 'Recettes asiatiques')"),
    workers: int = typer.Option(1, help="Nombre de claude -p en parallèle (1 = séquentiel)"),
    profile: str = typer.Option(None, help="Profil d'analyse (override env COLLECTION_PROFILE)"),
):
    """Phase 2 (V0) : spawn Claude Code headless avec le skill instatrip-analyze."""
    s = Settings.load()
    profile_name = profile or s.collection_profile
    run_analysis(
        project_root=s.project_root,
        trip_context=trip_context,
        n_workers=workers,
        profile_name=profile_name,
    )


@app.command()
def export(
    excel: bool = typer.Option(True),
    obsidian: bool = typer.Option(True),
    profile: str = typer.Option(None, help="Profil d'export (override env COLLECTION_PROFILE)"),
):
    """Exporte les insights enrichis vers Excel et/ou Obsidian."""
    s = Settings.load()
    profile_name = profile or s.collection_profile
    insights: list[PostInsight] = []
    for p in sorted(s.enriched_dir.glob("*.json")):
        insights.append(PostInsight.model_validate_json(p.read_text(encoding="utf-8")))
    if excel:
        out = s.output_dir / f"{s.collection_slug}.xlsx"
        export_excel(insights, out, profile_name=profile_name)
        console.print(f"[green]✓ Excel: {out}")
    if obsidian:
        out = export_obsidian(insights, s.obsidian_dir, s.collection_slug, profile_name=profile_name)
        console.print(f"[green]✓ Obsidian index: {out}")


@app.command()
def run(
    url: str = typer.Option(None),
    trip_context: str = typer.Option(""),
    workers: int = typer.Option(1, help="Workers parallèles pour l'étape interpret"),
    frame_interval: float = typer.Option(2.0, help="Intervalle (s) entre frames OCR"),
    ocr_confidence: float = typer.Option(0.4, help="Seuil de confiance EasyOCR"),
    profile: str = typer.Option(None, help="Profil d'analyse (override env COLLECTION_PROFILE)"),
):
    """Pipeline complet : collect → scrape → interpret → export."""
    collect(url=url)
    scrape(force=False, frame_interval=frame_interval, ocr_confidence=ocr_confidence, frame_dedup=True, dedup_threshold=6)
    interpret(trip_context=trip_context, workers=workers, profile=profile)
    export(excel=True, obsidian=True, profile=profile)


@app.command()
def profiles():
    """Liste les profils d'analyse disponibles."""
    from .profiles import PROFILES
    for name in sorted(PROFILES):
        p = PROFILES[name]
        console.print(f"[cyan]{p.name}[/cyan]  — {p.description}")
        console.print(f"  catégories : {', '.join(p.categories)}")
        console.print(f"  attributs  : {', '.join(k for k, _ in p.attribute_fields)}")
        console.print("")


if __name__ == "__main__":
    app()
