---
name: instatrip-veille
description: Analyse approfondie de veille technique (profil tech d'InstaTrip). Pour chaque post enrichi, restitue intégralement le contenu de la vidéo (listes, étapes, commandes, prompts), relève les liens, analyse les dépôts GitHub à partir de leur README, et rend un verdict d'utilité argumenté. Écrit data/veille/<shortcode>.json. Utiliser quand un runner ou l'utilisateur invoque "instatrip-veille".
---

# instatrip-veille

## Objectif

Transformer chaque post en fiche de veille exploitable plus tard, sans revoir la vidéo. Le lecteur doit savoir **ce qui a été dit, ce que vaut la ressource, et comment l'essayer**.

## Entrées (dossier courant = la collection)

Pour un shortcode `<sc>` :
- `data/raw/<sc>.json` : `caption`, `transcript` (la voix de la vidéo), `ocr_text` (le texte affiché à l'écran, une entrée par plan, souvent bruité : lettres collées, caractères parasites), `pinned_comment`.
- `data/enriched/<sc>.json` : catégorie, titre, description, `attributes` (repos, outils, stack, cas_usage, mot_cle_cta).
- `data/resolved/<sc>.json` : dépôts résolus (`full_name`, `confidence`, étoiles, licence...).
- `data/repos/<owner>__<nom>.json` pour chaque dépôt résolu : `readme`, `topics`, `homepage`, `latest_release`, `open_issues`, `forks`, `created_at`, `pushed_at`, `archived`.

## Procédure

1. Lister les shortcodes à traiter (liste fournie dans l'invocation, sinon tous les `data/enriched/*.json`). Ignorer ceux qui ont déjà `data/veille/<sc>.json` (compter en `skipped`).
2. Pour chaque post, lire les fichiers ci-dessus puis écrire `data/veille/<sc>.json` (UTF-8, indenté) :

```json
{
  "shortcode": "<sc>",
  "contenu": "markdown",
  "liens": [{"url": "https://...", "label": "..."}],
  "verdict": "utile | a-creuser | gadget | hors-sujet",
  "pertinence": 1,
  "analyse": "markdown",
  "comment_tester": "markdown",
  "limites": ["..."],
  "idees_projets": ["..."],
  "repos": {
    "<owner>/<nom>": {
      "resume": "...",
      "fonctionnalites": ["..."],
      "installation": "...",
      "maturite": "...",
      "correspondance_video": "ok | douteuse | fausse"
    }
  }
}
```

3. Écrire la sentinelle (`data/.veille.done` ou `data/.veille.done.<worker_id>`) au même format que instatrip-analyze : `status`, `processed`, `skipped`, `failed`, `failures`, `finished_at` (UTC, suffixe Z). Toujours l'écrire, même en cas d'échec partiel.

## Règles de rédaction par champ

**`contenu`** : restitution fidèle et complète de ce que dit et montre la vidéo, pas un résumé.
- Une liste annoncée (« 20 trucs », « 5 outils », « 3 erreurs ») est restituée **en entier**, numérotée, chaque point reformulé clairement en une ligne, avec sa justification si la vidéo en donne une. Croiser `transcript` et `ocr_text` pour reconstituer les points ; si un point manque, l'écrire `(point non audible / non lisible)` plutôt que de l'inventer.
- Étapes d'installation, commandes, noms d'outils, prompts : les recopier. Un prompt va dans un bloc de code.
- Corriger les déformations évidentes de la transcription (ex. « Cores » → CORS, « webbooks » → webhooks, « guide ignore » → .gitignore), sans ajouter d'information.
- Si la vidéo n'apporte rien au-delà du titre (teaser, « commente pour recevoir »), le dire en une phrase.

**`liens`** : toutes les URL trouvées (caption, OCR, transcription, commentaire épinglé) plus l'URL de chaque dépôt et sa `homepage`. Pas de lien inventé.

**`repos`** : à partir du README et des signaux, pas de la vidéo seule.
- `resume` : ce que fait réellement le projet, en 2 phrases.
- `fonctionnalites` : 3 à 6 points tirés du README.
- `installation` : la méthode réelle (npm, pip, docker, binaire, extension...) et ses prérequis (GPU, clé API payante, OS).
- `maturite` : âge, dernier push, release, étoiles, issues ouvertes, licence ; signaler archivé, licence restrictive (AGPL, non commerciale, absente), projet d'une semaine sans release.
- `correspondance_video` : le dépôt correspond-il à ce que montre la vidéo ? `fausse` si le README parle d'autre chose (le dépôt a été mal résolu).

**`verdict`** et **`pertinence`** (1 à 5) : jugés pour le lecteur décrit dans l'invocation.
- `utile` : apporte un gain concret et réutilisable ; `a-creuser` : prometteur mais à vérifier (jeune, flou, prérequis lourds) ; `gadget` : effet démo, peu d'usage réel ou déjà couvert par mieux ; `hors-sujet` : sans rapport avec un usage de dev.
- **`analyse`** : pourquoi ce verdict. Pour quel type de projet, ce que ça remplace ou complète, les alternatives connues si elles sont évidentes. Être franc : signaler l'exagération marketing (« remplace Adobe », « 30k/mois »), les conseils faux ou dépassés.
- **`comment_tester`** : 2 à 5 étapes concrètes pour l'essayer en moins d'une heure (commande d'install, premier cas d'usage). Pour une astuce ou une liste, transformer en action vérifiable (ex. checklist à passer sur un projet existant).
- **`limites`** : risques et coûts (sécurité, données envoyées à un tiers, coût d'API, maintenance, licence).
- **`idees_projets`** : 1 à 3 usages concrets dans des projets perso du lecteur.

## Interdits

- Ne pas modifier `data/raw`, `data/enriched`, `data/resolved`, `data/repos`.
- Pas d'appel réseau : tout le contexte est dans les fichiers.
- Ne jamais inventer un point de liste, un lien, une commande ou une fonctionnalité absente des données.
- Rédiger en français, sans formules creuses ; les identifiants techniques restent en anglais.
