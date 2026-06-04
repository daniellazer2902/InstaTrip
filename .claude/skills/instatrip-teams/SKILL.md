---
name: instatrip-teams
description: Analyse une vidéo Teams ingérée (data/bundle.json) d'une collection InstaTrip et produit le chapitrage (data/analysis/chapter_NN.json) + la synthèse globale (data/analysis/synthesis.json), puis propose l'export Obsidian. Utiliser quand l'utilisateur veut analyser une vidéo Teams, traiter un bundle Teams, ou invoque "instatrip-teams". Mode interactif (PAS de claude -p headless).
---

# instatrip-teams

## Objectif

Transformer `data/bundle.json` (produit par `instatrip teams ingest`) en :
- une note d'analyse par chapitre : `data/analysis/chapter_NN.json`
- une synthèse globale : `data/analysis/synthesis.json`

Le contexte type est la présentation d'un projet de développement par un dév à un autre.

## Procédure interactive (l'utilisateur suit en direct)

1. **Vérifier le bundle.** Si `data/bundle.json` absent : proposer de lancer
   `uv run instatrip teams ingest --collection <slug>` en Bash, puis continuer.

2. **Lire `data/bundle.json`.** Chaque `window` contient : `index`, `start`, `end`,
   `transcript`, `frames[]` (chacune avec `timecode`, `path`, `ocr`).

3. **Chapitrage — une fenêtre = un chapitre** (les fenêtres sont déjà des découpages
   temporels de ~15 min). Pour chaque window, écrire `data/analysis/chapter_NN.json`
   (NN = index sur 2 chiffres) conforme au schéma `ChapterAnalysis` :

   ```json
   {
     "index": 0,
     "title": "Titre court et parlant du chapitre",
     "start": 0.0,
     "themes": ["theme-1", "theme-2"],
     "key_points": [{"text": "...", "timecode": 742.0}],
     "decisions": [{"text": "décision technique", "timecode": 1810.0}],
     "frames": [{"timecode": 906.0, "path": "data/frames/frame_063.jpg", "ocr": "..."}],
     "transcript_excerpt": "extrait représentatif (2-4 phrases)"
   }
   ```

   - `title` : déduit du contenu (transcript + OCR des frames).
   - `themes` : 2-5 mots-clés kebab-case français.
   - `key_points` / `decisions` : points importants et décisions techniques, avec le
     `timecode` (en secondes) du segment le plus pertinent de la fenêtre. Ne jamais inventer
     un timecode : reprendre `start` de la fenêtre ou le `timecode` d'une frame pertinente.
   - `frames` : ne garder que les frames RÉELLEMENT pertinentes du chapitre (slides/écrans
     de code utiles), pas toutes. Reprendre exactement `timecode`/`path`/`ocr` du bundle.
   - Ne JAMAIS inventer une donnée absente du transcript/OCR.

4. **Synthèse globale.** Après tous les chapitres, lire les `chapter_NN.json` (compacts) et
   écrire `data/analysis/synthesis.json` conforme au schéma `Synthesis` :

   ```json
   {
     "title": "Titre de la présentation",
     "summary": "Résumé exécutif (5-10 phrases) en français.",
     "themes": ["transverse-1", "transverse-2"],
     "key_points": [{"text": "...", "timecode": 742.0}],
     "decisions": [{"text": "...", "timecode": 1810.0}],
     "todos": ["question ouverte ou point à clarifier"],
     "chapters": [{"index": 0, "title": "...", "start": 0.0}]
   }
   ```

   - `chapters` doit lister TOUS les chapitres écrits (index, title, start cohérents).
   - `summary` synthétise l'ensemble de la présentation, pas un seul chapitre.

5. **Proposer l'export.** Annoncer que l'analyse est terminée et proposer :
   `uv run instatrip teams export --collection <slug>` pour générer le dossier Obsidian.

## Règles

- **Ne pas modifier `data/bundle.json` ni `data/frames/`.**
- **Pas de sentinelle, pas de `claude -p`** : tout se fait dans la session courante, visible.
- **Pas d'outils externes** (pas de WebFetch) : tout le contexte est dans `bundle.json`.
- Tous les timecodes sont en **secondes** (l'exporter les formate en HH:MM:SS).
- JSON pretty-printed, UTF-8, sans BOM.
