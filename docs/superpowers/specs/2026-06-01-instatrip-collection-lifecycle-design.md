# InstaTrip — Cycle de vie des collections, robustesse & onboarding

Date : 2026-06-01
Statut : validé (design)

## Contexte

InstaTrip est un pipeline Instagram saved → Excel + Obsidian, organisé en
collections (`collections/<slug>/`). Le pipeline a 4 phases CLI : `collect`
(scroll → shortcodes), `scrape` (DL + transcription + OCR), `interpret`
(analyse LLM via skill `instatrip-analyze`), `export` (Excel + Obsidian).

Cette itération couvre 3 chantiers indépendants, à livrer dans l'ordre A → B → C :

- **A** — Corrections de bugs détectés en production.
- **B** — Skill invocable de cycle de vie d'une collection (init / reprise).
- **C** — Onboarding et garde-fous pour un nouvel utilisateur.

Hors scope : le cœur OCR/Whisper, les exporters Excel/Obsidian, les profils
d'analyse.

---

## Chantier A — Corrections de bugs

### A1. BOM UTF-8 + robustesse de `interpret`

**Problème.** `interpret_runner.py` lit les sentinelles des workers avec
`read_text(encoding="utf-8")`. Quand un worker Claude écrit la sentinelle JSON
avec un BOM UTF-8, `json.loads` lève
`JSONDecodeError: Unexpected UTF-8 BOM`. Observé en session : les 11 posts
étaient correctement enrichis, mais le runner a crashé à la lecture de la
sentinelle du worker 0 — laissant les sentinelles des workers 1/2/3 non
consommées.

**Correction.**
1. Lire les sentinelles en `encoding="utf-8-sig"` aux deux emplacements :
   `_run_single` (~L100) et `_run_parallel` (~L164).
2. Rendre l'agrégation parallèle **tolérante aux pannes** :
   - Un worker dont la sentinelle est absente, illisible, ou en `status:error`
     est consigné dans `failures` (avec `shortcode`/`worker` + message), **sans**
     faire échouer toute la run tant qu'au moins un worker a réussi.
   - `status` global = `error` uniquement si **tous** les workers ont échoué ;
     sinon `ok`, avec les pannes listées dans `failures`.
   - Les sentinelles consommées sont toujours `unlink()` (y compris en erreur)
     pour ne pas polluer la run suivante.

**Critères d'acceptation.**
- Une sentinelle écrite avec un BOM est lue sans erreur.
- Si 1 worker sur 4 échoue, les 3 autres sont agrégés et la commande retourne
  `status:ok` avec 1 entrée dans `failures`.
- Si tous les workers échouent, `SentinelError` est levée.

### A2. Posts images / carrousel (sans yt-dlp)

**Problème.** `media.download_media` route **tout** par yt-dlp. Sur un post
photo/carrousel, l'extracteur Instagram de yt-dlp lève
`No video formats found`, l'exception remonte et `extract_one` perd le post
(8 posts perdus en session).

**Correction.** Découpler la détection du type média de yt-dlp.

1. `post_page.fetch_post` renvoie en plus :
   - `is_video: bool`
   - `image_urls: list[str]` (ordonnées ; 1 pour un post simple, N pour un
     carrousel).
   - Détection vidéo : présence d'une balise `<video>` ou d'un
     `og:video`/`og:type=video` dans la page.
   - Carrousel : Playwright clique la flèche « Suivant » (`aria-label`
     "Next"/"Suivant") tant qu'elle est présente, en collectant à chaque slide
     le `src` haute résolution des `<img>` du post (force le lazy-load).
     Déduplication des URLs. Garde-fou : max ~20 itérations pour éviter une
     boucle infinie.
2. `media.py` :
   - `download_video(shortcode, ...)` : yt-dlp **uniquement** pour la vidéo
     (logique actuelle, format vidéo seulement).
   - `download_images(image_urls, media_dir, shortcode)` : télécharge les bytes
     en HTTP avec les cookies IG (les URLs CDN `og:image` sont en général
     accessibles), sauvegarde `<shortcode>_0.jpg`, `<shortcode>_1.jpg`, …
     Retourne la liste des chemins.
   - `download_media` orchestre : si `is_video` → `download_video`, sinon
     `download_images`. Plus aucun appel yt-dlp pour les photos.
3. `extract.extract_one` :
   - Branche sur `is_video` (renvoyé par `fetch_post`) au lieu de la présence
     d'un `video_path` produit par yt-dlp.
   - `media_type` : `REEL` si vidéo, `CAROUSEL` si > 1 image, sinon `IMAGE`.
   - Le reste (OCR des images, écriture du JSON brut, cleanup) est inchangé.

**Critères d'acceptation.**
- Un des 8 shortcodes images-only de japon-2026 (ex. `DYcETg2CdRO`) produit un
  `data/raw/<sc>.json` avec `media_type` ∈ {IMAGE, CAROUSEL} et un `ocr_text`
  non vide quand l'image contient du texte.
- Aucun appel yt-dlp n'est émis pour un post photo.
- Un reel vidéo continue de passer exactement comme avant (transcription +
  OCR des frames).

---

## Chantier B — Skill `/instatrip-collection`

Point d'entrée **unique** qui branche init vs reprise.

### Fichier
`.claude/skills/instatrip-collection/SKILL.md` (même emplacement que
`instatrip-analyze`).

### Flux
1. **Pré-vol** : lancer `uv run instatrip doctor`. Si le cookie IG est périmé,
   afficher la marche à suivre (`uv run instatrip auth`) et **s'arrêter**.
2. **Choix de la collection** : lister l'existant via
   `uv run instatrip collections`, puis demander à l'utilisateur la collection
   cible (nom).
   - **Existe déjà → reprise** : `uv run instatrip run --collection <slug>
     --trip-context "<contexte>" --workers 4`. Le pipeline est idempotent :
     seuls les nouveaux posts sont traités. Rapporter le **nombre de nouveaux
     posts** (delta du nombre de fichiers `data/enriched/*.json` avant/après).
   - **N'existe pas → init** : demander (a) le **lien de la collection IG**,
     (b) le **profil** (`voyage` par défaut / `recettes` / `sport`), (c) un
     **contexte** optionnel. Scaffolder via
     `uv run instatrip new <slug> --url <url> --profile <profil>`, puis lancer
     le pipeline complet comme ci-dessus.
3. **Rapport final** : nb de posts traités, échecs éventuels, et chemins de
   sortie (`collections/<slug>/output/<slug>.xlsx` + `output/obsidian/`).

### Support CLI
Nouvelle commande `instatrip new` :
```
instatrip new <slug> --url <url> [--profile voyage]
```
- Crée `collections/<slug>/` et écrit `collections/<slug>/.env` avec
  `COLLECTION_URL`, `COLLECTION_SLUG`, `COLLECTION_PROFILE`.
- Refuse si la collection existe déjà et que son `.env` est présent (évite
  l'écrasement) ; message clair invitant à utiliser la reprise.
- La reprise réutilise la commande `run` existante (aucune nouvelle CLI).

**Critères d'acceptation.**
- Invoquer la skill sur un slug existant lance la reprise et rapporte le delta.
- Invoquer sur un slug inconnu demande lien + profil, crée le `.env`, lance le
  pipeline.
- `instatrip new` sur une collection existante échoue proprement sans écraser.

---

## Chantier C — Onboarding & garde-fous

### C1. Commande `instatrip doctor`
Nouvelle commande CLI. Vérifie et affiche OK / ⚠ / KO + commande de réparation :

| Check | OK si | Réparation affichée |
|---|---|---|
| ffmpeg | `ffmpeg -version` répond | `winget install Gyan.FFmpeg` |
| CLI claude | `claude --version` répond | installer Claude Code CLI |
| Chromium Playwright | navigateur installé | `uv run playwright install chromium` |
| torch / CUDA | torch importable (CUDA = info, pas KO) | `uv sync` (CUDA optionnel) |
| Session IG | `.secrets/ig_state.json` présent + `sessionid` non expiré | `uv run instatrip auth` |

- Sortie tableau Rich. Code retour non-zéro si au moins un check **bloquant**
  (ffmpeg, claude, chromium, session) est KO ; CUDA absent n'est jamais
  bloquant.

### C2. Santé du cookie IG
- Util `session.check_session(state_path) -> {status, expires_at, days_left}` :
  lit `ig_state.json`, trouve le cookie `sessionid` (domaine instagram), compare
  `expires` à maintenant.
  - `status` ∈ `missing` (fichier/cookie absent) / `expired` / `expiring`
    (< 7 jours) / `fresh`.
- Réutilisé par `doctor` et par le pré-vol.
- Note : pas de `Date.now` interdit ici (code Python normal, `time.time()`).

### C3. Pré-vol dans `collect` / `scrape`
- Au début de `collect` et `scrape`, appeler `check_session` ; si `expired` ou
  `missing`, afficher un **warning non bloquant** invitant à `auth` (l'opération
  continue — l'utilisateur peut vouloir réessayer un cookie limite).

### C4. `run.bat` (bootstrap complet)
À la racine du projet. Séquence :
1. Vérifier que `uv` est installé ; sinon afficher le lien d'install et quitter.
2. `uv sync`
3. `uv run playwright install chromium`
4. Lancer `claude` avec un **prompt d'onboarding** qui :
   - explique en 2 lignes ce que fait InstaTrip,
   - invoque la skill `/instatrip-collection`,
   - rappelle que l'analyse passe par l'abonnement Claude Code (aucune clé API).

### C5. `SETUP.md`
Document d'install pas-à-pas à la racine :
- Prérequis (Python 3.12, uv, ffmpeg, Claude Code CLI, GPU NVIDIA optionnel).
- Installation (`uv sync`, `playwright install chromium`).
- **Cookie / session IG** : comment fonctionne `.secrets/ig_state.json`,
  comment le créer/rafraîchir via `uv run instatrip auth` (login Playwright
  manuel), comment vérifier sa fraîcheur via `uv run instatrip doctor`, et la
  note sur le remplacement manuel du fichier si besoin.
- Démarrage rapide : `run.bat` ou `uv run instatrip` + `/instatrip-collection`.

**Critères d'acceptation.**
- `uv run instatrip doctor` affiche le tableau et un code retour non-zéro si un
  check bloquant échoue.
- `run.bat` sur une machine fraîche (uv installé) amène jusqu'au prompt
  d'onboarding sans étape manuelle supplémentaire.
- `SETUP.md` permet à un nouvel utilisateur d'installer et de lancer sans aide.

---

## Nettoyage opportuniste
- `config.py` mentionne `ANTHROPIC_API_KEY` alors que l'analyse passe par l'abo
  Claude Code. À documenter comme optionnel (ne pas casser la signature) — pas
  de suppression dans cette itération pour rester focalisé.

## Ordre de livraison
A1 → A2 → (vérif sur japon-2026 : re-scrape des 8 posts photo) → B → C.
