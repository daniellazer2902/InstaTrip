from __future__ import annotations

import json
import shutil
from pathlib import Path

import typer
from rich.console import Console

from .auth import login_and_save_state
from .collection import collect_shortcodes
from .config import Settings
from .doctor import build_report, has_blocking_failure
from .exporters.excel import export_excel
from .exporters.obsidian import export_obsidian
from .extract import extract_all
from .interpret_runner import run_analysis
from .models import PostInsight
from .scaffold import scaffold_collection
from .session import session_warning

app = typer.Typer(add_completion=False, no_args_is_help=True)
teams_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(teams_app, name="teams", help="Mode Teams : analyser une vidéo locale.")
console = Console()


def _collection_opt():
    return typer.Option(None, help="Slug de la collection (sous-dossier collections/<slug>/). Override env COLLECTION_SLUG.")


@app.command()
def auth():
    """Connexion Instagram (1 fois). Sauvegarde la session (partagée par toutes les collections)."""
    s = Settings.load()
    login_and_save_state(s.state_path)


@app.command()
def collect(
    url: str = typer.Option(None, help="URL de la collection (défaut: env COLLECTION_URL)"),
    collection: str = _collection_opt(),
):
    """Scrolle la collection et écrit la liste des shortcodes."""
    s = Settings.load(collection=collection)
    warn = session_warning(s.state_path)
    if warn:
        console.print(f"[yellow]{warn}")
    target = url or s.collection_url
    if not target:
        raise typer.BadParameter("Fournir --url ou définir COLLECTION_URL dans .env")
    codes = collect_shortcodes(target, s.state_path)
    s.shortcodes_file.write_text(json.dumps(codes, indent=2), encoding="utf-8")
    console.print(f"[green]✓ {len(codes)} shortcodes → {s.shortcodes_file}")


@app.command()
def scrape(
    force: bool = typer.Option(False, help="Force re-download"),
    frame_interval: float = typer.Option(2.0, help="Intervalle (s) entre frames OCR."),
    ocr_confidence: float = typer.Option(0.4, help="Seuil de confiance EasyOCR (0-1)."),
    frame_dedup: bool = typer.Option(True, help="Dédup les frames quasi-identiques (dHash) avant OCR."),
    dedup_threshold: int = typer.Option(6, help="Distance Hamming max pour dédup (0-64)."),
    dedup_mode: str = typer.Option("bands", help="'bands' (top+bottom 30%) ou 'full' (image entière)."),
    collection: str = _collection_opt(),
):
    """Phase 1 : extraction brute pour chaque shortcode."""
    s = Settings.load(collection=collection)
    warn = session_warning(s.state_path)
    if warn:
        console.print(f"[yellow]{warn}")
    codes = json.loads(s.shortcodes_file.read_text(encoding="utf-8"))
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
    trip_context: str = typer.Option("", help="Contexte (ex: 'Voyage Japon 2026')"),
    workers: int = typer.Option(1, help="Nombre de claude -p en parallèle (1 = séquentiel)"),
    profile: str = typer.Option(None, help="Profil d'analyse (override env COLLECTION_PROFILE)"),
    collection: str = _collection_opt(),
):
    """Phase 2 : spawn Claude Code headless avec le skill instatrip-analyze."""
    s = Settings.load(collection=collection)
    profile_name = profile or s.collection_profile
    run_analysis(
        collection_root=s.collection_root,
        trip_context=trip_context,
        n_workers=workers,
        profile_name=profile_name,
    )


@app.command()
def export(
    excel: bool = typer.Option(True),
    obsidian: bool = typer.Option(True),
    profile: str = typer.Option(None, help="Profil d'export (override env COLLECTION_PROFILE)"),
    collection: str = _collection_opt(),
):
    """Exporte les insights enrichis vers Excel et/ou Obsidian."""
    s = Settings.load(collection=collection)
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
    frame_interval: float = typer.Option(2.0),
    ocr_confidence: float = typer.Option(0.4),
    profile: str = typer.Option(None, help="Profil d'analyse"),
    collection: str = _collection_opt(),
):
    """Pipeline complet : collect → scrape → interpret → export."""
    collect(url=url, collection=collection)
    scrape(force=False, frame_interval=frame_interval, ocr_confidence=ocr_confidence,
           frame_dedup=True, dedup_threshold=6, dedup_mode="bands", collection=collection)
    interpret(trip_context=trip_context, workers=workers, profile=profile, collection=collection)
    export(excel=True, obsidian=True, profile=profile, collection=collection)


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


@app.command()
def collections():
    """Liste les collections présentes dans collections/."""
    root = Path.cwd() / "collections"
    if not root.exists():
        console.print("[yellow]Aucune collection (dossier 'collections/' absent).")
        return
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        raw_count = len(list((sub / "data" / "raw").glob("*.json"))) if (sub / "data" / "raw").exists() else 0
        enr_count = len(list((sub / "data" / "enriched").glob("*.json"))) if (sub / "data" / "enriched").exists() else 0
        console.print(f"[cyan]{sub.name}[/cyan]  raw={raw_count}  enriched={enr_count}")


@app.command()
def new(
    slug: str = typer.Argument(..., help="Slug de la nouvelle collection (ex: tokyo-2027)"),
    url: str = typer.Option(..., help="URL de la collection Instagram (dossier Enregistrements)"),
    profile: str = typer.Option("voyage", help="Profil d'analyse (voyage / recettes / sport)"),
):
    """Crée une nouvelle collection (collections/<slug>/.env)."""
    try:
        env = scaffold_collection(Path.cwd(), slug, url, profile)
    except FileExistsError as e:
        raise typer.BadParameter(str(e))
    console.print(f"[green]✓ Collection créée : {env}")
    console.print(f"[dim]Lance : uv run instatrip run --collection {slug}")


@app.command()
def doctor():
    """Vérifie l'environnement (ffmpeg, claude, chromium, torch, session IG)."""
    from rich.table import Table

    s = Settings.load()
    report = build_report(s.state_path)
    table = Table(title="InstaTrip — doctor")
    table.add_column("Check")
    table.add_column("Statut")
    table.add_column("Détail / Réparation")
    icon = {"ok": "[green]OK", "warn": "[yellow]⚠", "ko": "[red]KO"}
    for c in report:
        fix = c.detail if c.status == "ok" else (c.detail + " — " + c.hint if c.detail else c.hint)
        table.add_row(c.name, icon[c.status], fix)
    console.print(table)
    if has_blocking_failure(report):
        console.print("[red]✗ Au moins un prérequis bloquant manque.")
        raise typer.Exit(1)
    console.print("[green]✓ Environnement OK.")


@app.command()
def migrate(
    to: str = typer.Argument(..., help="Slug cible (ex: japon-2026). Les fichiers data/ et output/ y sont déplacés."),
):
    """Migration one-shot : déplace l'ancienne structure (data/, output/) vers collections/<slug>/."""
    root = Path.cwd()
    target = root / "collections" / to
    if target.exists() and any(target.iterdir()):
        raise typer.BadParameter(f"{target} existe déjà et n'est pas vide.")
    target.mkdir(parents=True, exist_ok=True)

    moved: list[str] = []
    old_data = root / "data"
    old_output = root / "output"
    if old_data.exists():
        shutil.move(str(old_data), str(target / "data"))
        moved.append("data/")
    if old_output.exists():
        shutil.move(str(old_output), str(target / "output"))
        moved.append("output/")

    # renomme l'ancien <slug>-shortcodes.json → shortcodes.json
    old_sc = target / "data" / f"{to}-shortcodes.json"
    new_sc = target / "data" / "shortcodes.json"
    if old_sc.exists() and not new_sc.exists():
        old_sc.rename(new_sc)
        moved.append(f"{to}-shortcodes.json → shortcodes.json")

    if not moved:
        console.print("[yellow]Rien à migrer.")
        return
    console.print(f"[green]✓ Migration vers collections/{to}/ : {', '.join(moved)}")
    console.print("[dim]N'oublie pas : mets à jour .env avec COLLECTION_SLUG si besoin.")


@teams_app.command("new")
def teams_new(slug: str = typer.Argument(..., help="Slug (ex: demo-projet-x)")):
    """Crée collections/<slug>/input/ — dépose ta vidéo Teams dedans."""
    from .scaffold import scaffold_teams
    try:
        env = scaffold_teams(Path.cwd(), slug)
    except FileExistsError as e:
        raise typer.BadParameter(str(e))
    console.print(f"[green]✓ Collection Teams créée : {env}")
    console.print(f"[dim]Dépose la vidéo dans collections/{slug}/input/ puis : uv run instatrip teams ingest --collection {slug}")


@teams_app.command("ingest")
def teams_ingest(
    model: str = typer.Option("medium", help="Modèle Whisper (tiny/base/small/medium/large-v3)."),
    frame_interval: float = typer.Option(2.0, help="Intervalle (s) entre frames."),
    window_minutes: float = typer.Option(15.0, help="Durée d'une fenêtre de chapitrage (min)."),
    dedup_threshold: int = typer.Option(6, help="Distance Hamming max pour dédup frames."),
    dedup_mode: str = typer.Option("bands", help="'bands' ou 'full'."),
    ocr_confidence: float = typer.Option(0.4, help="Seuil de confiance OCR."),
    collection: str = _collection_opt(),
):
    """Extraction : audio -> transcription -> frames -> OCR -> data/bundle.json."""
    from .teams import ingest
    s = Settings.load(collection=collection)
    bundle = ingest(
        input_dir=s.input_dir,
        data_dir=s.collection_root / "data",
        slug=s.collection_slug,
        model_size=model,
        frame_interval=frame_interval,
        window_minutes=window_minutes,
        dedup_threshold=dedup_threshold,
        dedup_mode=dedup_mode,
        ocr_confidence=ocr_confidence,
    )
    console.print(f"[green]✓ Bundle écrit : {bundle}")
    console.print("[dim]Étape suivante : invoque le skill instatrip-teams pour analyser (chapitrage + synthèse).")


@teams_app.command("export")
def teams_export(collection: str = _collection_opt()):
    """Génère le dossier Obsidian depuis data/analysis/ (synthesis + chapitres)."""
    from .exporters.obsidian_teams import export_teams_obsidian
    from .teams_models import ChapterAnalysis, Synthesis
    s = Settings.load(collection=collection)
    analysis = s.collection_root / "data" / "analysis"
    syn_path = analysis / "synthesis.json"
    if not syn_path.exists():
        raise typer.BadParameter(f"Synthèse absente : {syn_path}. Lance d'abord le skill instatrip-teams.")
    synthesis = Synthesis.model_validate_json(syn_path.read_text(encoding="utf-8"))
    chapters = [
        ChapterAnalysis.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(analysis.glob("chapter_*.json"))
    ]
    out_dir = s.obsidian_dir / s.collection_slug
    index = export_teams_obsidian(synthesis, chapters, out_dir, slug=s.collection_slug)
    console.print(f"[green]✓ Obsidian : {index}")


if __name__ == "__main__":
    app()
