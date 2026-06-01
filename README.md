# InstaTrip

Pipeline Instagram saved → Excel + Obsidian pour analyser **n'importe quelle collection thématique** (voyage, recettes, sport…) à partir d'un dossier IG "Enregistrements".

## Démarrage rapide

**Le plus simple (Windows)** : double-clique `run.bat`. Il installe tout et lance un assistant Claude qui te guide (cf. `SETUP.md`).

**Manuellement** :
```
uv sync
uv run playwright install chromium
uv run instatrip doctor          # vérifie ffmpeg, claude, chromium, GPU, session IG
uv run instatrip auth            # 1× : login Instagram
```
Puis, dans Claude Code, invoque **`/instatrip-collection`** : il crée une nouvelle collection (en demandant le lien Instagram) ou reprend une collection existante pour récupérer les nouveaux posts. Détails d'installation et gestion du cookie : voir **`SETUP.md`**.

## Confidentialité

La session Instagram (`.secrets/ig_state.json`), le fichier `.env` et les données de collection (`collections/*/data`, `collections/*/output`) sont **ignorés par Git** et ne doivent jamais être publiés. Copie `.env.example` vers `.env` pour ta config locale.

## Organisation multi-collections

Chaque collection vit dans son propre sous-dossier :

```
INstaTrip/
├── .env                            # config par défaut (slug, profile, url)
├── .secrets/ig_state.json          # session IG (PARTAGÉE entre toutes les collections)
└── collections/
    ├── japon-2026/                 # une collection voyage
    │   ├── .env                    # (optionnel) override de la config racine
    │   ├── data/
    │   │   ├── raw/
    │   │   ├── enriched/
    │   │   ├── media/
    │   │   └── shortcodes.json
    │   └── output/
    │       ├── japon-2026.xlsx
    │       └── obsidian/
    │           ├── *.md
    │           └── japon-2026.base
    ├── recettes-asiatiques/        # une collection recettes
    │   └── ...
    └── pull-ups-progression/       # une collection sport
        └── ...
```

Sélection de la collection active :
- via env : `COLLECTION_SLUG=japon-2026` dans `.env`
- via CLI : `--collection japon-2026` sur n'importe quelle commande (override)

Créer une nouvelle collection : `uv run instatrip new <slug> --url "<lien IG>" --profile voyage`.

Lister les collections existantes : `uv run instatrip collections`.

Diagnostiquer l'environnement (ffmpeg, claude, chromium, GPU, session IG) : `uv run instatrip doctor`.

Migration one-shot depuis l'ancienne structure (flat `data/` + `output/` au root) : `uv run instatrip migrate <slug>`.

## Profils d'analyse

Chaque profil = un domaine (catégories possibles, attributs extraits, template Obsidian Base adapté). Profils livrés :

| Profil | Catégories | Attributs extraits |
|---|---|---|
| `voyage` (défaut) | lieu, tips, activite, autre | city, neighborhood, activity |
| `recettes` | plat, dessert, boisson, technique, ingredient, autre | cuisine, difficulte, temps, ingredients_cles |
| `sport` | cardio, musculation, mobilite, technique, programme, autre | groupe_musculaire, equipement, niveau, duree |

Lister les profils dispos : `uv run instatrip profiles`.

Sélectionner un profil : `COLLECTION_PROFILE=recettes` dans `.env`, ou `--profile recettes` en CLI sur `interpret` / `export` / `run`.

Chaque profil génère son **propre `.base` Obsidian** avec des vues adaptées (ex: recettes filtre par cuisine/difficulté, sport groupe par muscle/matériel). Tu peux ajouter un nouveau profil en créant `src/instatrip/profiles/<nom>.py` (voir `voyage.py` comme template).

## Prérequis

- **Python 3.12** + [uv](https://docs.astral.sh/uv/) (gestionnaire de deps)
- **ffmpeg** sur le PATH (`winget install Gyan.FFmpeg`)
- **Claude Code CLI** (`claude --version` doit fonctionner) — l'analyse V0 délègue à Claude Code en headless via ton abonnement (aucune clé API séparée)
- **GPU NVIDIA + CUDA** (optionnel mais fortement recommandé — voir section dédiée)

## Setup

```
uv sync
uv run playwright install chromium
cp .env.example .env
# éditer .env : COLLECTION_URL, COLLECTION_SLUG
```

## Usage — cas nominal

```
uv run instatrip auth                                              # 1× : login manuel Instagram
uv run instatrip collect                                           # scrolle la collection → shortcodes
uv run instatrip scrape                                            # phase 1 : DL + transcription + OCR
uv run instatrip interpret --trip-context "Voyage Japon 2026" --workers 4   # phase 2 : analyse LLM
uv run instatrip export                                            # Excel + Obsidian
```

ou tout en un :

```
uv run instatrip run --trip-context "Voyage Japon 2026" --workers 4
```

### Reprise après erreur

Chaque étape est **idempotente avec cache par shortcode** :
- `scrape` skip les posts dont `data/raw/<shortcode>.json` existe déjà
- `interpret` skip ceux dont `data/enriched/<shortcode>.json` existe déjà
- → re-lancer la même commande continue là où ça s'était arrêté

Pour forcer un re-traitement : `--force` sur `scrape`, ou supprimer manuellement le JSON du post à re-traiter.

## Architecture

| Phase | Module | Entrée | Sortie | Coût |
|---|---|---|---|---|
| 1. **Scrape** | `extract.py` | shortcodes | `data/raw/<sc>.json` | local (Playwright + yt-dlp + Whisper + EasyOCR) |
| 2. **Interpret** | `interpret_runner.py` → skill | `data/raw/` | `data/enriched/<sc>.json` + sentinelle `data/.enriched.done[.N]` | abonnement Claude Code (aucun overage) |
| 3. **Export** | `exporters/` | `data/enriched/` | `output/<slug>.xlsx` + `output/obsidian/` | local |

Les fichiers médias intermédiaires (mp4, wav, frames jpg) sont **supprimés automatiquement** une fois le JSON brut écrit pour économiser le disque. Les JSONs sont la source de vérité.

## Accélération GPU (recommandé)

Avec une GPU NVIDIA + CUDA, Whisper et EasyOCR passent sur GPU automatiquement (détection via `torch.cuda.is_available()`).

**Speedup constaté** : ~5× sur un RTX 4060 Laptop (33 s/post vs 150 s/post CPU).

Si CUDA n'est pas installé, fallback CPU silencieux (Whisper int8, EasyOCR `gpu=False`). Pour installer PyTorch CUDA, le `pyproject.toml` pointe déjà vers l'index `pytorch-cu128` — un simple `uv sync` télécharge les wheels CUDA (~4 GB).

## Options CLI avancées

### `scrape` — ajuster qualité OCR vs vitesse

| Option | Défaut | Effet |
|---|---|---|
| `--frame-interval 2.0` | 2 s | Intervalle entre frames vidéo échantillonnées. `1.0` = 2× plus de frames (+50% temps). |
| `--ocr-confidence 0.4` | 0.4 | Seuil EasyOCR (0-1). Plus haut = moins de bruit, mais perte de texte flou. |
| `--frame-dedup / --no-frame-dedup` | ON | Skip les frames quasi-identiques (dHash perceptuel) avant OCR. |
| `--dedup-threshold 6` | 6 | Distance Hamming max pour considérer 2 frames identiques (0-64). Plus bas = plus strict. |
| `--dedup-mode bands` | `bands` | `bands` = hash top+bottom 30% (cible overlays texte IG). `full` = hash image entière. |
| `--force` | off | Re-télécharge et re-traite tous les posts (ignore cache). |

**Exemples** :

```
# Plus de frames (gain d'info, coût +50%)
uv run instatrip scrape --frame-interval 1.0

# Moins de bruit OCR
uv run instatrip scrape --ocr-confidence 0.6

# Dedup plus strict (capte changements de texte plus subtils)
uv run instatrip scrape --dedup-threshold 3

# Forcer un re-scrape complet avec params différents
uv run instatrip scrape --force --frame-interval 1.0 --dedup-threshold 4
```

### `interpret` — parallélisation LLM

| Option | Défaut | Effet |
|---|---|---|
| `--trip-context "..."` | (vide) | Contexte voyage donné au LLM (ex: destination, dates). |
| `--workers N` | 1 | Nombre de `claude -p` lancés en parallèle. **4 est un bon choix** pour ~100 posts. |

**Important** : `--workers 4` spawn 4 instances Claude Code simultanément, toutes tirant sur **ton abonnement Claude Code** (même quota, pas de frais supplémentaires). Speedup ~3.5-4×.

```
uv run instatrip interpret --trip-context "Voyage Japon 2026" --workers 4
```

### `export` — formats

| Option | Défaut | Effet |
|---|---|---|
| `--excel / --no-excel` | ON | Génère `output/<slug>.xlsx` |
| `--obsidian / --no-obsidian` | ON | Génère 1 note `.md` par post + 1 index groupé par ville |

## Sentinelle phase 2 (technique)

Le skill `instatrip-analyze` écrit `data/.enriched.done` (ou `.enriched.done.<worker_id>` en mode parallèle) avec :

```json
{
  "status": "ok" | "error",
  "processed": <int>,
  "skipped": <int>,
  "failed": <int>,
  "failures": [{"shortcode": "...", "error": "..."}],
  "finished_at": "<ISO8601 UTC Z>"
}
```

Le runner Python lit, consomme (`unlink`), et agrège les stats. Permet aussi le mode hors-CC : lancer manuellement `claude` dans le projet et invoquer le skill.

## Limitations connues

- **Compatibilité OCR EasyOCR** : `["en", "ja"]` uniquement (le français n'est pas combinable avec le japonais — limitation EasyOCR). Le texte français passe via la transcription Whisper et la caption IG.
- **Posts inaccessibles** : ~5-10 % des shortcodes d'une collection peuvent être indisponibles (compte privé, post supprimé, erreur IG temporaire). Échec silencieux par post, le pipeline continue.
- **Rate limit Instagram** : 1 session Playwright + 1 stream yt-dlp à la fois — la parallélisation phase 1 risquerait un ban.
- **Console Windows cp1252** : les emojis Rich peuvent crasher PowerShell 5.1. Workaround : `$env:PYTHONIOENCODING="utf-8"` avant chaque commande.

## Outputs

- `output/<slug>.xlsx` : 1 ligne par post (Shortcode, URL, Catégorie, Titre, Ville, Quartier, Description, Activité, Tags)
- `output/obsidian/<slug>.md` : index (à la racine) groupé par ville + section Tips
- `output/obsidian/<slug>.base` : base Obsidian interactive (à la racine)
- `output/obsidian/posts/<shortcode>.md` : 1 note par post (frontmatter YAML + wikilink `[[Ville]]`), regroupées dans le sous-dossier `posts/`
