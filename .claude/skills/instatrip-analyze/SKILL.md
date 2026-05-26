---
name: instatrip-analyze
description: Analyse les posts Instagram bruts (data/raw/*.json) d'une collection et produit un JSON enrichi par post (data/enriched/<shortcode>.json) selon le profil d'analyse fourni (voyage, recettes, sport, etc.). Utiliser quand l'utilisateur ou un runner invoque "instatrip-analyze" ou demande d'analyser les posts InstaTrip.
---

# instatrip-analyze

## Objectif

Pour chaque fichier `data/raw/<shortcode>.json` du projet courant, produire `data/enriched/<shortcode>.json` qui suit ce schéma universel :

```json
{
  "shortcode": "...",
  "url": "...",
  "category": "<valeur du profil>",
  "title": "...",
  "description": "1-3 phrases en français",
  "tags": ["...", "..."],
  "attributes": {
    "<champ_profil_1>": "...",
    "<champ_profil_2>": "..."
  }
}
```

**Les valeurs de `category` et la liste des `attributes` dépendent du profil**, qui est fourni dans le prompt d'invocation sous "Domain-specific instruction". Lis-le attentivement avant de commencer.

## Procédure (à exécuter de manière déterministe)

1. **Lire les arguments d'invocation** :
   - **Profile** + **Domain-specific instruction** : définit les `category` valides et les champs `attributes` à remplir
   - **User context** (ex: "Voyage Japon 2026") : utilisé pour orienter le ton et les choix (le contexte voyage Japon biaise vers la classification fine de lieux japonais, etc.)
   - **Worker ID** (optionnel, entier) : si fourni, la sentinelle finale est `data/.enriched.done.<worker_id>` au lieu de `data/.enriched.done`
   - **Shortcodes** (optionnel, liste explicite) : si fournie, ne traiter QUE ces shortcodes. Sinon, traiter tous les `data/raw/*.json`

2. **Lister** les fichiers à traiter (liste fournie OU `data/raw/*.json`)

3. **Filtrer** ceux qui ont déjà un `data/enriched/<shortcode>.json` existant — les compter dans `skipped` (idempotence)

4. **Pour chaque post restant** :
   - Lire le JSON brut (champs : caption, pinned_comment, transcript, ocr_text, author, url, media_type)
   - Suivre l'**instruction du profil** pour : choisir la `category`, remplir `title` + `description` + `tags`, et remplir les `attributes` spécifiques au profil
   - Description : 1 à 3 phrases en français, factuelle, mentionne le "plus" / l'intérêt principal
   - Tags : 2-5 mots-clés courts en kebab-case français
   - Ne JAMAIS inventer une donnée non présente. Si une `attribute` est incertaine, mettre `null` ou omettre
   - Écrire `data/enriched/<shortcode>.json` (JSON pretty-printed, UTF-8)

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

   En cas d'échec global (ex: dossier `data/raw` introuvable), écrire `status: "error"` avec un champ `error`. Les autres champs restent présents (valeurs à 0 / `[]` si rien n'a tourné).

## Règles

- **Ne pas modifier `data/raw/`**
- **Ne pas appeler d'outils externes** (pas de WebFetch). Tout le contexte est dans les JSONs et l'instruction du profil
- **Toujours écrire la sentinelle**, même partiellement, à la toute fin — le runner Python en dépend
- En cas de doute sur une `attribute`, mettre `null` plutôt qu'inventer
- La catégorie doit être l'une des valeurs autorisées par le profil — JAMAIS une catégorie inventée
