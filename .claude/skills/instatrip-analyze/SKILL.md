---
name: instatrip-analyze
description: Analyse les posts Instagram bruts (data/raw/*.json) d'un voyage et produit un JSON enrichi par post (data/enriched/<shortcode>.json) avec catégorie, ville, quartier, description et tags. Utiliser quand l'utilisateur ou un runner invoque "instatrip-analyze" ou demande d'analyser les posts InstaTrip d'une collection.
---

# instatrip-analyze

## Objectif

Pour chaque fichier `data/raw/<shortcode>.json` du projet courant, produire `data/enriched/<shortcode>.json` qui suit ce schéma :

```json
{
  "shortcode": "...",
  "url": "...",
  "category": "lieu|tips|activite|autre",
  "title": "...",
  "city": "..." | null,
  "neighborhood": "..." | null,
  "description": "1-3 phrases en français",
  "activity": "..." | null,
  "tags": ["...", "..."]
}
```

## Procédure (à exécuter de manière déterministe)

1. **Lire les arguments d'invocation** :
   - **Trip context** (ex: "Voyage Japon 2026") — à défaut, déduire depuis le nom de la collection.
   - **Worker ID** (optionnel, entier) — si fourni, la sentinelle finale est `data/.enriched.done.<worker_id>` au lieu de `data/.enriched.done`.
   - **Shortcodes** (optionnel, liste explicite) — si fournie, ne traiter QUE ces shortcodes. Sinon, traiter tous les `data/raw/*.json`.
2. **Lister** les fichiers à traiter : la liste fournie OU `data/raw/*.json`.
3. **Filtrer** ceux qui ont déjà un `data/enriched/<shortcode>.json` — les compter dans `skipped` (idempotence).
4. **Pour chaque post restant** :
   - Lire le JSON brut (champs : caption, pinned_comment, transcript, ocr_text, author, url, media_type).
   - Classifier : `lieu` (resto, hôtel, point d'intérêt précis), `tips` (conseils généraux non liés à un lieu unique), `activite` (expérience à faire), `autre` (non exploitable).
   - Si lieu/activité : extraire `city` et `neighborhood` quand l'info est explicite. Ne JAMAIS inventer une ville. Si incertain, mettre `null`.
   - Description : 1 à 3 phrases en français, factuelle, mentionne le "plus" / l'intérêt principal.
   - Tags : 2 à 5 mots-clés courts en kebab-case français (`ramen`, `vue-panoramique`, `petit-dejeuner`).
   - Écrire `data/enriched/<shortcode>.json` (JSON pretty-printed, UTF-8).
5. **Sentinelle de fin** : écrire `data/.enriched.done` (ou `data/.enriched.done.<worker_id>` si worker_id fourni) avec :

```json
{
  "status": "ok",
  "processed": <int>,
  "skipped": <int>,
  "failed": <int>,
  "failures": [{"shortcode": "...", "error": "..."}],
  "finished_at": "<ISO8601 UTC, suffixe Z>"
}
```

   Invariants obligatoires :
   - `len(failures) == failed`
   - `finished_at` au format UTC avec suffixe `Z` (ex: `2026-05-26T14:30:00Z`)

   En cas d'échec global (ex: dossier `data/raw` introuvable), écrire `status: "error"` avec un champ `error`. Les autres champs (`processed`, `skipped`, `failed`, `failures`, `finished_at`) restent présents (valeurs à 0 / `[]` si rien n'a tourné).

## Règles

- **Ne pas modifier `data/raw/`**.
- **Ne pas appeler d'outils externes** (pas de WebFetch). Tout le contexte est dans les JSONs.
- **Toujours écrire la sentinelle**, même partiellement, à la toute fin — le runner Python en dépend.
- En cas de doute sur un champ, mettre `null` plutôt qu'inventer.
