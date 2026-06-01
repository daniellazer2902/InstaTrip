# InstaTrip — Cycle de vie collections, robustesse & onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fiabiliser le pipeline (bug BOM + posts images), ajouter une skill de cycle de vie de collection (init/reprise), et un onboarding nouvel utilisateur (doctor, santé cookie, run.bat, SETUP.md).

**Architecture:** Corrections ciblées dans les modules existants (`interpret_runner`, `post_page`, `media`, `extract`), deux nouveaux petits modules (`session.py`, `doctor.py`, `scaffold.py`), de nouvelles commandes CLI Typer (`new`, `doctor`), une skill Markdown, et des fichiers d'onboarding à la racine.

**Tech Stack:** Python 3.12, Typer, Rich, Playwright, yt-dlp, httpx, Pydantic, pytest. Tests via `uv run pytest`.

---

## Structure des fichiers

| Fichier | Responsabilité | Action |
|---|---|---|
| `src/instatrip/interpret_runner.py` | Lecture sentinelles tolérante au BOM + agrégation robuste | Modifier |
| `src/instatrip/post_page.py` | Détection vidéo + extraction URLs images | Modifier |
| `src/instatrip/media.py` | Split download vidéo / images | Modifier |
| `src/instatrip/extract.py` | Branche sur `is_video` | Modifier |
| `src/instatrip/session.py` | Santé du cookie IG | Créer |
| `src/instatrip/doctor.py` | Checks d'environnement | Créer |
| `src/instatrip/scaffold.py` | Création d'une collection | Créer |
| `src/instatrip/cli.py` | Commandes `new`, `doctor` + pré-vol | Modifier |
| `.claude/skills/instatrip-collection/SKILL.md` | Skill init/reprise | Créer |
| `run.bat` | Bootstrap + lancement onboarding | Créer |
| `SETUP.md` | Doc installation + cookie | Créer |
| `tests/test_interpret_runner.py` | Tests BOM + tolérance | Modifier |
| `tests/test_post_page_parse.py` | Test `parse_post_media` | Modifier |
| `tests/test_media_download.py` | Test `download_images` | Créer |
| `tests/test_session.py` | Test `check_session` | Créer |
| `tests/test_doctor.py` | Test logique doctor | Créer |
| `tests/test_scaffold.py` | Test scaffold collection | Créer |

---

## Chantier A — Bugs

### Task 1 : BOM + agrégation tolérante (`interpret_runner.py`)

**Files:**
- Modify: `src/instatrip/interpret_runner.py`
- Test: `tests/test_interpret_runner.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/test_interpret_runner.py` :

```python
def test_run_analysis_single_reads_sentinel_with_bom(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sentinel = data_dir / ".enriched.done"

    def fake_run(cmd, cwd, timeout, check):
        # Claude écrit parfois avec un BOM UTF-8
        sentinel.write_text(
            "﻿" + json.dumps({
                "status": "ok", "processed": 2, "skipped": 0, "failed": 0,
                "failures": [], "finished_at": "2026-05-26T10:00:00Z",
            }),
            encoding="utf-8",
        )
        class R: returncode = 0
        return R()

    with patch("instatrip.interpret_runner.subprocess.run", side_effect=fake_run):
        stats = run_analysis(project_root=tmp_path, trip_context="x")
    assert stats["status"] == "ok"
    assert stats["processed"] == 2


def test_run_analysis_parallel_tolerates_one_failed_worker(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    for sc in ["A", "B", "C", "D"]:
        (raw / f"{sc}.json").write_text("{}", encoding="utf-8")

    def fake_popen(cmd, cwd):
        prompt = cmd[2]
        worker_id = int(prompt.split("Worker ID: ")[1].split(".")[0])
        sentinel = tmp_path / "data" / f".enriched.done.{worker_id}"
        if worker_id == 0:
            # worker 0 n'écrit PAS sa sentinelle (panne)
            pass
        else:
            sentinel.write_text(
                ("﻿" if worker_id == 1 else "") + json.dumps({
                    "status": "ok", "processed": 1, "skipped": 0, "failed": 0,
                    "failures": [], "finished_at": "2026-05-26T10:00:00Z",
                }),
                encoding="utf-8",
            )
        class P:
            def wait(self, timeout=None): return 0
        return P()

    with patch("instatrip.interpret_runner.subprocess.Popen", side_effect=fake_popen):
        stats = run_analysis(project_root=tmp_path, n_workers=4)

    assert stats["status"] == "ok"          # au moins un worker a réussi
    assert stats["processed"] >= 1
    assert any("worker" in f for f in stats["failures"])  # panne consignée


def test_run_analysis_parallel_all_workers_fail_raises(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "A.json").write_text("{}", encoding="utf-8")

    def fake_popen(cmd, cwd):
        class P:
            def wait(self, timeout=None): return 0
        return P()  # aucune sentinelle écrite

    with patch("instatrip.interpret_runner.subprocess.Popen", side_effect=fake_popen):
        with pytest.raises(SentinelError):
            run_analysis(project_root=tmp_path, n_workers=2)
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run: `uv run pytest tests/test_interpret_runner.py -v`
Expected: les 3 nouveaux tests échouent (BOM → JSONDecodeError ; tolérance → SentinelError levée à tort).

- [ ] **Step 3 : Corriger `_run_single`**

Dans `src/instatrip/interpret_runner.py`, `_run_single`, remplacer la ligne :

```python
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
```

par :

```python
    payload = json.loads(sentinel.read_text(encoding="utf-8-sig"))
```

- [ ] **Step 4 : Réécrire l'agrégation de `_run_parallel`**

Remplacer le bloc d'agrégation (de `aggregated = {` jusqu'au `return aggregated` final, ~L153-179) par :

```python
    aggregated = {
        "status": "ok",
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }
    ok_workers = 0
    for wid in range(len(buckets)):
        s = collection_root / "data" / f"{SENTINEL_NAME}.{wid}"
        if not s.exists():
            aggregated["failures"].append({"worker": wid, "error": "sentinelle absente"})
            aggregated["failed"] += 1
            continue
        try:
            payload = json.loads(s.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            aggregated["failures"].append({"worker": wid, "error": f"sentinelle illisible: {e}"})
            aggregated["failed"] += 1
            s.unlink()
            continue
        s.unlink()
        if payload.get("status") != "ok":
            aggregated["failures"].append({"worker": wid, "error": payload.get("error", "status non-ok")})
            aggregated["failed"] += 1
            continue
        ok_workers += 1
        aggregated["processed"] += payload.get("processed", 0)
        aggregated["skipped"] += payload.get("skipped", 0)
        aggregated["failed"] += payload.get("failed", 0)
        aggregated["failures"].extend(payload.get("failures", []))

    if ok_workers == 0:
        raise SentinelError(
            f"Tous les workers ont échoué : {aggregated['failures']}"
        )

    console.print(
        f"[green]✓ analyse parallèle OK — processed={aggregated['processed']} "
        f"skipped={aggregated['skipped']} failed={aggregated['failed']}"
    )
    return aggregated
```

- [ ] **Step 5 : Lancer les tests, vérifier le succès**

Run: `uv run pytest tests/test_interpret_runner.py -v`
Expected: PASS (anciens + nouveaux tests).

- [ ] **Step 6 : Commit**

```bash
git add src/instatrip/interpret_runner.py tests/test_interpret_runner.py
git commit -m "fix(interpret): lecture sentinelle utf-8-sig + agregation parallele tolerante aux pannes"
```

---

### Task 2 : Détection vidéo + URLs images (`post_page.py`)

**Files:**
- Modify: `src/instatrip/post_page.py`
- Test: `tests/test_post_page_parse.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/test_post_page_parse.py` :

```python
from instatrip.post_page import parse_post_media


def test_parse_post_media_detects_video():
    html = """
    <html><head>
      <meta property="og:type" content="video.other">
      <meta property="og:video" content="https://cdn/v.mp4">
      <meta property="og:image" content="https://cdn/thumb.jpg">
    </head><body></body></html>
    """
    data = parse_post_media(html)
    assert data["is_video"] is True


def test_parse_post_media_image_post_returns_image_url():
    html = """
    <html><head>
      <meta property="og:type" content="instapp:photo">
      <meta property="og:image" content="https://cdn/photo.jpg">
    </head><body></body></html>
    """
    data = parse_post_media(html)
    assert data["is_video"] is False
    assert data["image_urls"] == ["https://cdn/photo.jpg"]
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_post_page_parse.py -v`
Expected: FAIL `ImportError: cannot import name 'parse_post_media'`.

- [ ] **Step 3 : Ajouter `parse_post_media` et augmenter `fetch_post`**

Dans `src/instatrip/post_page.py`, ajouter après `parse_post_html` :

```python
def parse_post_media(html: str) -> dict:
    """Détecte le type média d'une page de post Instagram.

    Renvoie {is_video: bool, image_urls: list[str]}. Pour un carrousel,
    le HTML statique n'expose souvent que la 1re image (og:image) ; les
    slides suivantes sont collectées par fetch_post via Playwright."""
    soup = BeautifulSoup(html, "html.parser")
    og_type = soup.find("meta", attrs={"property": "og:type"})
    og_video = soup.find("meta", attrs={"property": "og:video"})
    type_val = (og_type["content"] if og_type and og_type.get("content") else "").lower()
    is_video = bool(og_video) or "video" in type_val

    image_urls: list[str] = []
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        image_urls.append(og_image["content"])
    return {"is_video": is_video, "image_urls": image_urls}
```

Puis, dans `fetch_post`, après `html = page.content()` et **avant** `browser.close()`, collecter les images de carrousel et fusionner. Remplacer le corps de la boucle `with sync_playwright()` à partir de `html = page.content()` par :

```python
        html = page.content()
        media = parse_post_media(html)
        image_urls = list(media["image_urls"])
        if not media["is_video"]:
            # Carrousel : cliquer "Suivant" pour forcer le lazy-load de chaque slide
            for _ in range(20):  # garde-fou anti-boucle
                for img in page.query_selector_all("article img"):
                    src = img.get_attribute("src")
                    if src and src.startswith("http") and src not in image_urls:
                        image_urls.append(src)
                nxt = page.query_selector("button[aria-label='Next'], button[aria-label='Suivant']")
                if not nxt:
                    break
                try:
                    nxt.click(timeout=1000)
                    page.wait_for_timeout(600)
                except Exception:
                    break
        browser.close()
    data = parse_post_html(html)
    data["url"] = url
    data["is_video"] = media["is_video"]
    data["image_urls"] = image_urls
    return data
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_post_page_parse.py -v`
Expected: PASS (test parse existant + 2 nouveaux).

- [ ] **Step 5 : Commit**

```bash
git add src/instatrip/post_page.py tests/test_post_page_parse.py
git commit -m "feat(post_page): detection video + extraction urls images (carrousel via swipe)"
```

---

### Task 3 : Split download vidéo / images (`media.py`)

**Files:**
- Modify: `src/instatrip/media.py`
- Test: `tests/test_media_download.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_media_download.py` :

```python
from instatrip.media import download_images, download_media


def test_download_images_writes_files(tmp_path, monkeypatch):
    class FakeResp:
        content = b"\xff\xd8imagedata"
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()
    monkeypatch.setattr("instatrip.media.httpx.Client", FakeClient)

    paths = download_images(["http://x/1.jpg", "http://x/2.jpg"], tmp_path, "ABC")
    assert len(paths) == 2
    assert paths[0].name == "ABC_0.jpg"
    assert paths[0].read_bytes() == b"\xff\xd8imagedata"


def test_download_media_image_post_skips_ytdlp(tmp_path, monkeypatch):
    class FakeResp:
        content = b"img"
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()
    monkeypatch.setattr("instatrip.media.httpx.Client", FakeClient)
    # si yt-dlp était appelé, ce patch ferait planter le test
    monkeypatch.setattr("instatrip.media.yt_dlp", None)

    result = download_media(
        "ABC", state_path=tmp_path / "state.json", media_dir=tmp_path / "m",
        is_video=False, image_urls=["http://x/1.jpg"],
    )
    assert result["video_path"] is None
    assert len(result["image_paths"]) == 1
    assert result["media_type"] == "image"
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_media_download.py -v`
Expected: FAIL `ImportError: cannot import name 'download_images'`.

- [ ] **Step 3 : Refactor `media.py`**

Dans `src/instatrip/media.py`, remplacer la fonction `download_media` (L30-61) par les trois fonctions suivantes (garder `export_cookies_netscape` au-dessus, inchangée) :

```python
def download_video(shortcode: str, state_path: Path, media_dir: Path) -> Optional[Path]:
    """Télécharge la vidéo d'un reel via yt-dlp (format vidéo uniquement)."""
    media_dir.mkdir(parents=True, exist_ok=True)
    cookies = media_dir.parent / ".cookies.txt"
    export_cookies_netscape(state_path, cookies)

    url = f"https://www.instagram.com/p/{shortcode}/"
    out_tpl = str(media_dir / f"{shortcode}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_tpl,
        "cookiefile": str(cookies),
        "quiet": True,
        "no_warnings": True,
        "writeinfojson": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    for f in media_dir.glob(f"{shortcode}.*"):
        if f.suffix.lower() in {".mp4", ".mov", ".webm"}:
            return f
    return None


def download_images(image_urls: list[str], media_dir: Path, shortcode: str) -> list[Path]:
    """Télécharge les bytes des images d'un post photo/carrousel via HTTP."""
    media_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for i, url in enumerate(image_urls):
            r = client.get(url)
            r.raise_for_status()
            p = media_dir / f"{shortcode}_{i}.jpg"
            p.write_bytes(r.content)
            paths.append(p)
    return paths


def download_media(
    shortcode: str,
    state_path: Path,
    media_dir: Path,
    is_video: bool,
    image_urls: Optional[list[str]] = None,
) -> dict:
    """Orchestrateur : vidéo → yt-dlp, sinon téléchargement HTTP des images.
    Plus aucun appel yt-dlp pour les posts photo (fini le crash
    'No video formats found')."""
    if is_video:
        video_path = download_video(shortcode, state_path, media_dir)
        return {"video_path": video_path, "image_paths": [], "media_type": "reel"}
    paths = download_images(image_urls or [], media_dir, shortcode)
    return {
        "video_path": None,
        "image_paths": paths,
        "media_type": "carousel" if len(paths) > 1 else "image",
    }
```

Ajouter en haut du fichier l'import (après `import yt_dlp`) :

```python
import httpx
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_media_download.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/instatrip/media.py tests/test_media_download.py
git commit -m "feat(media): split download video/images, posts photo sans yt-dlp"
```

---

### Task 4 : Brancher `extract_one` sur `is_video` (`extract.py`)

**Files:**
- Modify: `src/instatrip/extract.py:48-77`

- [ ] **Step 1 : Modifier `extract_one`**

Dans `src/instatrip/extract.py`, remplacer les lignes 48-77 (de `console.print(f"[cyan]→ {shortcode}: fetch page")` jusqu'à la ligne calculant `media_type = MediaType.CAROUSEL`) par :

```python
    console.print(f"[cyan]→ {shortcode}: fetch page")
    page = fetch_post(shortcode, settings.state_path)

    console.print(f"[cyan]→ {shortcode}: download media")
    media = download_media(
        shortcode,
        settings.state_path,
        settings.media_dir,
        is_video=page.get("is_video", False),
        image_urls=page.get("image_urls", []),
    )

    transcript: str | None = None
    ocr_text: list[str] = []
    if media["video_path"]:
        wav = settings.media_dir / f"{shortcode}.wav"
        extract_audio(media["video_path"], wav)
        console.print(f"[cyan]→ {shortcode}: transcribe")
        transcript = transcribe(wav)

        frames_dir = settings.media_dir / f"{shortcode}_frames"
        frames = sample_frames(media["video_path"], frames_dir, every_seconds=frame_interval)
        if frame_dedup and frames:
            before = len(frames)
            frames = dedup_frames(frames, threshold=dedup_threshold, mode=dedup_mode)
            console.print(f"[dim]→ {shortcode}: dedup ({dedup_mode}) frames {before} → {len(frames)}")
        if frames:
            console.print(f"[cyan]→ {shortcode}: OCR {len(frames)} frames")
            ocr_text = ocr_images(frames, min_confidence=ocr_min_confidence)
    elif media["image_paths"]:
        console.print(f"[cyan]→ {shortcode}: OCR image(s)")
        ocr_text = ocr_images(media["image_paths"], min_confidence=ocr_min_confidence)

    if media["video_path"]:
        media_type = MediaType.REEL
    elif len(media["image_paths"]) > 1:
        media_type = MediaType.CAROUSEL
    else:
        media_type = MediaType.IMAGE
```

- [ ] **Step 2 : Lancer la suite complète**

Run: `uv run pytest -v`
Expected: PASS (aucune régression).

- [ ] **Step 3 : Commit**

```bash
git add src/instatrip/extract.py
git commit -m "feat(extract): branche sur is_video pour gerer reels et posts photo"
```

---

### Task 5 : Vérification réelle sur japon-2026

**Files:** aucun (vérification manuelle).

- [ ] **Step 1 : Re-scraper les posts photo perdus**

Run (PowerShell, à la racine du projet) :
```powershell
$env:PYTHONIOENCODING="utf-8"; uv run instatrip scrape --collection japon-2026
```
Expected: les shortcodes auparavant en échec `No video formats found` (ex. `DYcETg2CdRO`, `DYNG5f0mEWU`, `DVgYcJbDJ01`, `DVGZJsuDA-O`, `DTdK2AdjS9S`, `DTW6RfYEY6u`, `DTpoFt1APVS`, `DT4_5S9DWz0`, `DTtf-t0Es3O`) produisent maintenant `✓ <sc> saved`.

- [ ] **Step 2 : Vérifier les JSON bruts**

Run:
```powershell
(Get-ChildItem collections\japon-2026\data\raw\*.json | Measure-Object).Count
```
Expected: > 109 (les posts photo en plus).

- [ ] **Step 3 : Enrichir + exporter le delta**

Run:
```powershell
$env:PYTHONIOENCODING="utf-8"; uv run instatrip interpret --collection japon-2026 --trip-context "Voyage Japon 2026" --workers 4
$env:PYTHONIOENCODING="utf-8"; uv run instatrip export --collection japon-2026
```
Expected: nouveaux `data/enriched/*.json`, Excel + Obsidian régénérés, aucune `JSONDecodeError`.

- [ ] **Step 4 : Pas de commit** (données de collection, non versionnées).

---

## Chantier B — Skill de cycle de vie

### Task 6 : Scaffold d'une collection (`scaffold.py` + CLI `new`)

**Files:**
- Create: `src/instatrip/scaffold.py`
- Modify: `src/instatrip/cli.py`
- Test: `tests/test_scaffold.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_scaffold.py` :

```python
import pytest

from instatrip.scaffold import scaffold_collection


def test_scaffold_creates_env(tmp_path):
    env = scaffold_collection(tmp_path, "tokyo-2027", "https://insta/saved/x/", "voyage")
    assert env.exists()
    content = env.read_text(encoding="utf-8")
    assert "COLLECTION_SLUG=tokyo-2027" in content
    assert "COLLECTION_URL=https://insta/saved/x/" in content
    assert "COLLECTION_PROFILE=voyage" in content
    assert (tmp_path / "collections" / "tokyo-2027" / "data").is_dir()


def test_scaffold_refuses_existing(tmp_path):
    scaffold_collection(tmp_path, "tokyo-2027", "https://insta/x/", "voyage")
    with pytest.raises(FileExistsError):
        scaffold_collection(tmp_path, "tokyo-2027", "https://insta/y/", "voyage")
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_scaffold.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'instatrip.scaffold'`.

- [ ] **Step 3 : Créer `scaffold.py`**

```python
from __future__ import annotations

from pathlib import Path


def scaffold_collection(project_root: Path, slug: str, url: str, profile: str = "voyage") -> Path:
    """Crée collections/<slug>/ + .env. Refuse si le .env existe déjà."""
    col = project_root / "collections" / slug
    env = col / ".env"
    if env.exists():
        raise FileExistsError(
            f"La collection '{slug}' existe déjà ({env}). Utilise la reprise."
        )
    (col / "data").mkdir(parents=True, exist_ok=True)
    env.write_text(
        f"COLLECTION_URL={url}\n"
        f"COLLECTION_SLUG={slug}\n"
        f"COLLECTION_PROFILE={profile}\n",
        encoding="utf-8",
    )
    return env
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_scaffold.py -v`
Expected: PASS.

- [ ] **Step 5 : Ajouter la commande CLI `new`**

Dans `src/instatrip/cli.py`, ajouter l'import en haut :

```python
from .scaffold import scaffold_collection
```

Puis ajouter cette commande (après `collections`) :

```python
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
```

- [ ] **Step 6 : Vérifier la CLI**

Run: `uv run instatrip new --help`
Expected: affiche l'aide de la commande `new` sans erreur.

- [ ] **Step 7 : Commit**

```bash
git add src/instatrip/scaffold.py src/instatrip/cli.py tests/test_scaffold.py
git commit -m "feat(cli): commande 'new' pour scaffolder une collection"
```

---

### Task 7 : Skill `/instatrip-collection`

**Files:**
- Create: `.claude/skills/instatrip-collection/SKILL.md`

- [ ] **Step 1 : Écrire la skill**

Créer `.claude/skills/instatrip-collection/SKILL.md` :

```markdown
---
name: instatrip-collection
description: Initie ou reprend une collection InstaTrip de bout en bout. Demande le lien de la collection Instagram pour une nouvelle collection, ou reprend une collection existante en allant chercher les nouveaux posts, puis traite et exporte vers Excel + Obsidian. Utiliser quand l'utilisateur veut créer/initialiser une collection InstaTrip, reprendre/mettre à jour une collection, ou récupérer les nouveaux posts d'une collection.
---

# instatrip-collection

Point d'entrée unique pour gérer une collection InstaTrip : **init** (nouvelle) ou **reprise** (existante). Toutes les commandes se lancent à la racine du projet InstaTrip, préfixées par `$env:PYTHONIOENCODING="utf-8";` sous PowerShell Windows.

## Procédure

### 1. Pré-vol (santé environnement + cookie)
Lance `uv run instatrip doctor`.
- Si un check **bloquant** est KO (ffmpeg, claude, chromium, session IG), affiche la réparation indiquée et **arrête-toi**.
- En particulier, si la **session IG est périmée/absente** : dis à l'utilisateur de lancer `uv run instatrip auth` (login manuel Playwright), puis de relancer la skill.

### 2. Choix de la collection
Lance `uv run instatrip collections` pour lister l'existant, puis demande à l'utilisateur quelle collection il veut traiter (nom/slug).

- **Si le slug existe déjà → REPRISE** :
  - Note le nombre actuel de posts : compte les fichiers `collections/<slug>/data/enriched/*.json`.
  - Lance `uv run instatrip run --collection <slug> --trip-context "<contexte>" --workers 4`.
  - Recompte les enriched ; rapporte le **nombre de nouveaux posts** (delta).

- **Si le slug n'existe pas → INIT** :
  - Demande à l'utilisateur : (a) le **lien de la collection Instagram** (dossier Enregistrements), (b) le **profil** (`voyage` par défaut, `recettes`, ou `sport`), (c) un **contexte** optionnel (ex: "Voyage Japon 2026").
  - Crée la collection : `uv run instatrip new <slug> --url "<lien>" --profile <profil>`.
  - Lance le pipeline : `uv run instatrip run --collection <slug> --trip-context "<contexte>" --workers 4`.

### 3. Rapport final
Indique : nombre de posts traités (et nouveaux), échecs éventuels (posts inaccessibles), et les chemins de sortie :
- Excel : `collections/<slug>/output/<slug>.xlsx`
- Obsidian : `collections/<slug>/output/obsidian/`

## Règles
- Ne jamais modifier les `data/raw/` ou `data/enriched/` à la main.
- Le pipeline est idempotent : une reprise ne retraite que les nouveaux posts.
- L'analyse passe par l'abonnement Claude Code (aucune clé API à fournir).
- Si l'utilisateur ne précise pas de contexte, passer une chaîne vide.
```

- [ ] **Step 2 : Vérifier la présence de la skill**

Run: `uv run instatrip collections` (sanity check que la CLI tourne — la skill elle-même est chargée par Claude Code au prochain démarrage de session).
Expected: liste des collections sans erreur.

- [ ] **Step 3 : Commit**

```bash
git add .claude/skills/instatrip-collection/SKILL.md
git commit -m "feat(skill): instatrip-collection (init/reprise guidee)"
```

---

## Chantier C — Onboarding & garde-fous

### Task 8 : Santé du cookie IG (`session.py`)

**Files:**
- Create: `src/instatrip/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_session.py` :

```python
import json
import time

from instatrip.session import check_session


def _write_state(path, expires):
    path.write_text(json.dumps({
        "cookies": [
            {"name": "sessionid", "domain": ".instagram.com", "expires": expires}
        ]
    }), encoding="utf-8")


def test_check_session_missing_file(tmp_path):
    res = check_session(tmp_path / "absent.json")
    assert res["status"] == "missing"


def test_check_session_expired(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() - 86400)
    res = check_session(p)
    assert res["status"] == "expired"


def test_check_session_fresh(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() + 86400 * 30)
    res = check_session(p)
    assert res["status"] == "fresh"
    assert res["days_left"] > 20


def test_check_session_expiring(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() + 86400 * 3)
    res = check_session(p)
    assert res["status"] == "expiring"
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_session.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'instatrip.session'`.

- [ ] **Step 3 : Créer `session.py`**

```python
from __future__ import annotations

import json
import time
from pathlib import Path


def check_session(state_path: Path) -> dict:
    """Évalue la fraîcheur du cookie sessionid Instagram.

    Renvoie {status, expires_at, days_left}.
    status ∈ {missing, expired, expiring (<7j), fresh}."""
    if not state_path.exists():
        return {"status": "missing", "expires_at": None, "days_left": None}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "missing", "expires_at": None, "days_left": None}

    sid = next(
        (c for c in state.get("cookies", [])
         if c.get("name") == "sessionid" and "instagram.com" in c.get("domain", "")),
        None,
    )
    if not sid:
        return {"status": "missing", "expires_at": None, "days_left": None}

    expires = sid.get("expires", -1)
    if not expires or expires < 0:
        # cookie de session sans expiration explicite — état inconnu, on suppose frais
        return {"status": "fresh", "expires_at": None, "days_left": None}

    days_left = (expires - time.time()) / 86400
    if days_left <= 0:
        status = "expired"
    elif days_left < 7:
        status = "expiring"
    else:
        status = "fresh"
    return {"status": status, "expires_at": expires, "days_left": days_left}


def session_warning(state_path: Path) -> str | None:
    """Message d'avertissement non bloquant si la session est périmée/absente."""
    res = check_session(state_path)
    if res["status"] in {"missing", "expired"}:
        return (
            "⚠ Session Instagram périmée ou absente. "
            "Lance `uv run instatrip auth` si le scraping échoue."
        )
    return None
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_session.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/instatrip/session.py tests/test_session.py
git commit -m "feat(session): check sante du cookie Instagram"
```

---

### Task 9 : Commande `doctor` (`doctor.py` + CLI)

**Files:**
- Create: `src/instatrip/doctor.py`
- Modify: `src/instatrip/cli.py`
- Test: `tests/test_doctor.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_doctor.py` :

```python
from instatrip.doctor import Check, has_blocking_failure, check_ig_session


def test_has_blocking_failure_true_when_blocking_ko():
    report = [
        Check(name="ffmpeg", status="ok", blocking=True, hint=""),
        Check(name="session", status="ko", blocking=True, hint="auth"),
    ]
    assert has_blocking_failure(report) is True


def test_has_blocking_failure_false_when_only_warn():
    report = [
        Check(name="cuda", status="warn", blocking=False, hint=""),
        Check(name="ffmpeg", status="ok", blocking=True, hint=""),
    ]
    assert has_blocking_failure(report) is False


def test_check_ig_session_expired_is_blocking_ko(tmp_path):
    import json, time
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"cookies": [
        {"name": "sessionid", "domain": ".instagram.com", "expires": time.time() - 10}
    ]}), encoding="utf-8")
    c = check_ig_session(p)
    assert c.blocking is True
    assert c.status == "ko"
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_doctor.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'instatrip.doctor'`.

- [ ] **Step 3 : Créer `doctor.py`**

```python
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .session import check_session


@dataclass
class Check:
    name: str
    status: str          # "ok" | "warn" | "ko"
    blocking: bool
    hint: str
    detail: str = ""


def _cmd_ok(args: list[str]) -> bool:
    try:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def check_ffmpeg() -> Check:
    ok = shutil.which("ffmpeg") is not None
    return Check("ffmpeg", "ok" if ok else "ko", True,
                 "winget install Gyan.FFmpeg")


def check_claude() -> Check:
    ok = _cmd_ok(["claude", "--version"])
    return Check("CLI claude", "ok" if ok else "ko", True,
                 "Installer Claude Code CLI")


def check_chromium() -> Check:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            path = pw.chromium.executable_path
            ok = bool(path) and Path(path).exists()
    except Exception:
        ok = False
    return Check("Chromium Playwright", "ok" if ok else "ko", True,
                 "uv run playwright install chromium")


def check_torch() -> Check:
    try:
        import torch
        cuda = torch.cuda.is_available()
        return Check("torch / CUDA", "ok" if cuda else "warn", False,
                     "uv sync (CUDA optionnel — fallback CPU)",
                     detail="CUDA actif" if cuda else "CPU uniquement")
    except Exception:
        return Check("torch / CUDA", "warn", False, "uv sync", detail="torch absent")


def check_ig_session(state_path: Path) -> Check:
    res = check_session(state_path)
    status_map = {"fresh": "ok", "expiring": "warn", "expired": "ko", "missing": "ko"}
    status = status_map.get(res["status"], "ko")
    detail = res["status"]
    if res.get("days_left") is not None:
        detail = f"{res['status']} ({res['days_left']:.0f} j restants)"
    return Check("Session IG", status, status == "ko",
                 "uv run instatrip auth", detail=detail)


def build_report(state_path: Path) -> list[Check]:
    return [
        check_ffmpeg(),
        check_claude(),
        check_chromium(),
        check_torch(),
        check_ig_session(state_path),
    ]


def has_blocking_failure(report: list[Check]) -> bool:
    return any(c.blocking and c.status == "ko" for c in report)
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_doctor.py -v`
Expected: PASS.

- [ ] **Step 5 : Ajouter la commande CLI `doctor`**

Dans `src/instatrip/cli.py`, ajouter l'import :

```python
from .doctor import build_report, has_blocking_failure
```

Puis la commande (après `new`) :

```python
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
```

- [ ] **Step 6 : Vérifier la CLI**

Run: `uv run instatrip doctor`
Expected: tableau Rich avec les 5 checks ; code retour 0 si tout est OK/warn.

- [ ] **Step 7 : Commit**

```bash
git add src/instatrip/doctor.py src/instatrip/cli.py tests/test_doctor.py
git commit -m "feat(cli): commande 'doctor' (checks env + sante cookie)"
```

---

### Task 10 : Pré-vol session dans `collect` / `scrape`

**Files:**
- Modify: `src/instatrip/cli.py`

- [ ] **Step 1 : Ajouter l'import**

Dans `src/instatrip/cli.py`, ajouter :

```python
from .session import session_warning
```

- [ ] **Step 2 : Pré-vol dans `collect`**

Dans la commande `collect`, juste après `s = Settings.load(collection=collection)`, ajouter :

```python
    warn = session_warning(s.state_path)
    if warn:
        console.print(f"[yellow]{warn}")
```

- [ ] **Step 3 : Pré-vol dans `scrape`**

Dans la commande `scrape`, juste après `s = Settings.load(collection=collection)`, ajouter le même bloc :

```python
    warn = session_warning(s.state_path)
    if warn:
        console.print(f"[yellow]{warn}")
```

- [ ] **Step 4 : Vérifier la suite + la CLI**

Run: `uv run pytest -v`
Expected: PASS.
Run: `uv run instatrip collections`
Expected: aucune erreur.

- [ ] **Step 5 : Commit**

```bash
git add src/instatrip/cli.py
git commit -m "feat(cli): pre-vol avertissement session sur collect/scrape"
```

---

### Task 11 : `run.bat` (bootstrap onboarding)

**Files:**
- Create: `run.bat`

- [ ] **Step 1 : Écrire `run.bat`**

Créer `run.bat` à la racine du projet :

```bat
@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo [InstaTrip] 'uv' introuvable. Installe-le : https://docs.astral.sh/uv/
  echo Puis relance run.bat
  pause
  exit /b 1
)

echo [InstaTrip] Installation des dependances (uv sync)...
call uv sync
if errorlevel 1 ( echo [InstaTrip] echec uv sync & pause & exit /b 1 )

echo [InstaTrip] Installation du navigateur Playwright...
call uv run playwright install chromium

echo [InstaTrip] Lancement de l'assistant Claude...
claude "Tu es l'assistant InstaTrip. InstaTrip transforme une collection Instagram 'Enregistrements' en fichier Excel + notes Obsidian. Invoque la skill instatrip-collection pour guider l'utilisateur (creation d'une nouvelle collection en demandant le lien Instagram, ou reprise d'une collection existante pour recuperer les nouveaux posts). Rappelle que l'analyse passe par l'abonnement Claude Code, sans cle API. Si la session Instagram est perimee, indique de lancer 'uv run instatrip auth'."

endlocal
```

- [ ] **Step 2 : Vérifier la syntaxe (lecture)**

Run: `type run.bat`
Expected: le contenu s'affiche sans caractère parasite.

- [ ] **Step 3 : Commit**

```bash
git add run.bat
git commit -m "feat(onboarding): run.bat bootstrap (uv sync + playwright + claude)"
```

---

### Task 12 : `SETUP.md`

**Files:**
- Create: `SETUP.md`

- [ ] **Step 1 : Écrire `SETUP.md`**

Créer `SETUP.md` à la racine :

```markdown
# InstaTrip — Installation & démarrage

InstaTrip transforme une collection Instagram « Enregistrements » en fichier
Excel + notes Obsidian, en analysant chaque post (transcription, OCR, LLM).

## Démarrage le plus simple (Windows)

Double-clique `run.bat`. Il installe les dépendances, le navigateur, puis
lance l'assistant Claude qui te guide pas à pas (création ou reprise d'une
collection). C'est tout.

## Prérequis (installation manuelle)

| Outil | Pourquoi | Installation |
|---|---|---|
| Python 3.12 | runtime | https://www.python.org/ |
| uv | gestionnaire de deps | https://docs.astral.sh/uv/ |
| ffmpeg | extraction audio/frames | `winget install Gyan.FFmpeg` |
| Claude Code CLI | analyse LLM (phase 2) | https://claude.com/claude-code |
| GPU NVIDIA + CUDA | *optionnel*, ~5× plus rapide | voir README, sinon fallback CPU |

## Installation

```
uv sync
uv run playwright install chromium
```

Vérifie que tout est prêt :

```
uv run instatrip doctor
```

`doctor` affiche l'état de ffmpeg, du CLI claude, de Chromium, de torch/CUDA,
et de ta **session Instagram**.

## Session / cookie Instagram

Le scraping a besoin d'être connecté à Instagram. La session est stockée dans
`.secrets/ig_state.json` (cookies + localStorage), **partagée par toutes les
collections**.

- **Créer / rafraîchir la session** :
  ```
  uv run instatrip auth
  ```
  Une fenêtre Chromium s'ouvre : connecte-toi manuellement à Instagram, puis
  reviens dans le terminal et appuie sur Entrée. La session est sauvegardée.

- **Vérifier la fraîcheur** : `uv run instatrip doctor` indique si le cookie
  `sessionid` est *frais*, *bientôt périmé* (< 7 jours) ou *périmé*.

- **Remplacement manuel** : tu peux remplacer `.secrets/ig_state.json` par un
  state Playwright exporté ailleurs, tant qu'il contient les cookies
  `instagram.com`. En pratique, relancer `auth` est plus simple.

> Si le scraping renvoie des posts inaccessibles en masse, la session est
> probablement périmée → relance `auth`.

## Utilisation

Le plus simple : l'assistant guidé.
```
claude
```
puis invoque `/instatrip-collection`.

Ou en CLI directe — voir `README.md` pour le détail des commandes
(`collect`, `scrape`, `interpret`, `export`, `run`, `new`, `collections`).
```

- [ ] **Step 2 : Commit**

```bash
git add SETUP.md
git commit -m "docs: SETUP.md (installation, cookie, demarrage)"
```

---

## Self-review (effectuée)

- **Couverture spec** : A1 (Task 1), A2 (Tasks 2-4), vérif (Task 5), B skill (Tasks 6-7), C1 doctor (Task 9), C2 session (Task 8), C3 pré-vol (Task 10), C4 run.bat (Task 11), C5 SETUP.md (Task 12). ✓
- **Cohérence des types** : `download_media(shortcode, state_path, media_dir, is_video, image_urls)` appelée identiquement dans `extract.py` (Task 4) et définie en Task 3. `check_session` renvoie `{status, expires_at, days_left}`, consommé par `doctor.check_ig_session` (Task 9) et `session_warning` (Task 8). `Check` dataclass définie Task 9, utilisée par les tests Task 9. `fetch_post` renvoie `is_video`/`image_urls` (Task 2), lus en Task 4. ✓
- **Pas de placeholder** : tout le code est explicite. ✓
```
