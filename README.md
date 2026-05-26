# InstaTrip

Pipeline Instagram saved → Excel/Obsidian pour préparer un voyage.

## Setup

```
uv sync
uv run playwright install chromium
cp .env.example .env
# éditer .env : COLLECTION_URL, COLLECTION_SLUG
```

Prérequis : `ffmpeg` sur le PATH (`winget install Gyan.FFmpeg`) et **Claude Code CLI** (`claude --version` doit fonctionner) — l'analyse V0 délègue à Claude Code en headless.

## Usage

```
uv run instatrip auth          # une fois : login manuel Instagram
uv run instatrip collect       # scrolle la collection → liste shortcodes
uv run instatrip scrape        # phase 1 : médias + transcription + OCR
uv run instatrip interpret --trip-context "Voyage Japon 2026"   # phase 2 : skill Claude Code
uv run instatrip export        # Excel + Obsidian
```

ou tout en un :

```
uv run instatrip run --trip-context "Voyage Japon 2026"
```

## Architecture

- Phase 1 (`extract.py`) : Playwright + yt-dlp + Whisper + EasyOCR → `data/raw/<shortcode>.json`
- Phase 2 V0 (`interpret_runner.py` → `claude -p` headless → skill `instatrip-analyze`) → `data/enriched/<shortcode>.json` + sentinelle `data/.enriched.done`
- Export : `output/<slug>.xlsx` + `output/obsidian/`

Idempotent : chaque étape utilise un cache par shortcode. Coût de la phase 2 visible via `/cost` dans la session Claude Code, ou les stats du fichier sentinelle.
