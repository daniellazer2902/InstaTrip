# InstaTrip — Installation & démarrage

InstaTrip transforme une collection Instagram « Enregistrements » en fichier
Excel + notes Obsidian, en analysant chaque post (transcription audio, OCR des
images/frames, puis classification par un LLM via Claude Code).

## Démarrage le plus simple (Windows)

Double-clique **`run.bat`**. Il installe les dépendances, le navigateur, puis
lance l'assistant Claude qui te guide pas à pas (création ou reprise d'une
collection). C'est tout.

## Prérequis (installation manuelle)

| Outil | Pourquoi | Installation |
|---|---|---|
| Python 3.12 | runtime | https://www.python.org/ |
| uv | gestionnaire de dépendances | https://docs.astral.sh/uv/ |
| ffmpeg | extraction audio / frames vidéo | `winget install Gyan.FFmpeg` |
| Claude Code CLI | analyse LLM (phase 2) | https://claude.com/claude-code |
| GPU NVIDIA + CUDA | *optionnel*, ~5× plus rapide | voir `README.md`, sinon fallback CPU |

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
et de ta **session Instagram**, avec la commande de réparation pour chaque ligne
en échec.

## Session / cookie Instagram

Le scraping a besoin d'être connecté à Instagram. La session est stockée dans
`.secrets/ig_state.json` (cookies + localStorage), **partagée par toutes les
collections**. Ce dossier est ignoré par Git (`.gitignore`) — il ne doit
**jamais** être publié.

- **Créer / rafraîchir la session** :
  ```
  uv run instatrip auth
  ```
  Une fenêtre Chromium s'ouvre : connecte-toi manuellement à Instagram, puis
  reviens dans le terminal et appuie sur Entrée. La session est sauvegardée.

- **Vérifier la fraîcheur** : `uv run instatrip doctor` indique si le cookie
  `sessionid` est *fresh*, *expiring* (< 7 jours) ou *expired*. Les commandes
  `collect` / `scrape` affichent aussi un avertissement non bloquant si la
  session est périmée.

- **Remplacement manuel** : tu peux remplacer `.secrets/ig_state.json` par un
  `storage_state` Playwright exporté ailleurs, tant qu'il contient les cookies
  `instagram.com`. En pratique, relancer `auth` est plus simple.

> Si le scraping renvoie beaucoup de posts inaccessibles, la session est
> probablement périmée → relance `auth`.

## Utilisation

Le plus simple : l'assistant guidé.
```
claude
```
puis invoque `/instatrip-collection` (création d'une nouvelle collection ou
reprise d'une existante pour récupérer les nouveaux posts).

En CLI directe, voir `README.md` pour le détail des commandes : `auth`,
`collect`, `scrape`, `interpret`, `export`, `run`, `new`, `collections`,
`doctor`.

## Sortie

- `collections/<slug>/output/<slug>.xlsx` — 1 ligne par post.
- `collections/<slug>/output/obsidian/` — l'**index** `<slug>.md` et la **base**
  `<slug>.base` à la racine ; les **notes par post** dans le sous-dossier
  `posts/`.
