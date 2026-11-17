---
name: instatrip-collection
description: Initie ou reprend une collection InstaTrip de bout en bout. Demande le lien de la collection Instagram pour une nouvelle collection, ou reprend une collection existante en allant chercher les nouveaux posts, puis traite et exporte vers Excel + Obsidian. Utiliser quand l'utilisateur veut créer/initialiser une collection InstaTrip, reprendre/mettre à jour une collection, ou récupérer les nouveaux posts d'une collection.
---

# instatrip-collection

Point d'entrée unique pour gérer une collection InstaTrip : **init** (nouvelle) ou **reprise** (existante). Toutes les commandes se lancent à la racine du projet InstaTrip. Sous PowerShell Windows, préfixe chaque commande par `$env:PYTHONIOENCODING="utf-8";` (évite les crashs d'encodage console).

## Procédure

### 1. Pré-vol (santé environnement + cookie)
Lance `uv run instatrip doctor`.
- Si un check **bloquant** est KO (ffmpeg, CLI claude, Chromium, Session IG), affiche la réparation indiquée par `doctor` et **arrête-toi**.
- En particulier, si la **Session IG** est périmée/absente : dis à l'utilisateur de lancer `uv run instatrip auth` (login manuel dans la fenêtre Chromium qui s'ouvre, puis Entrée dans le terminal), puis de relancer la skill.

### 2. Choix de la collection
Lance `uv run instatrip collections` pour lister l'existant, puis demande à l'utilisateur quelle collection il veut traiter (nom/slug).

- **Si le slug existe déjà → REPRISE** :
  - Note le nombre actuel de posts : compte les fichiers `collections/<slug>/data/enriched/*.json`.
  - Lance `uv run instatrip run --collection <slug> --trip-context "<contexte>" --workers 4`.
  - Recompte les enriched ; rapporte le **nombre de nouveaux posts** (delta).

- **Si le slug n'existe pas → INIT** :
  - Demande à l'utilisateur : (a) le **lien de la collection Instagram** (dossier Enregistrements, ex: `https://www.instagram.com/<user>/saved/<nom>/<id>/`), (b) le **profil** (`voyage` par défaut, `recettes`, `sport`, ou `tech` pour la veille repos GitHub / astuces IA), (c) un **contexte** optionnel (ex: "Voyage Japon 2026").
  - Crée la collection : `uv run instatrip new <slug> --url "<lien>" --profile <profil>`.
  - Lance le pipeline : `uv run instatrip run --collection <slug> --trip-context "<contexte>" --workers 4`.

### 3. Rapport final
Indique : nombre de posts traités (et nouveaux), échecs éventuels (posts inaccessibles : compte privé / supprimé), et les chemins de sortie :
- Excel : `collections/<slug>/output/<slug>.xlsx`
- Obsidian : `collections/<slug>/output/obsidian/` — l'**index** `<slug>.md` et la **base** `<slug>.base` sont à la racine, les **notes par post** sont dans le sous-dossier `posts/`.

**Profil `tech` uniquement** : `run` enchaîne aussi `resolve` (validation des noms de dépôts via `gh`) puis `vault` (une note par ressource dans `VAULT_VEILLE_DIR`, sous `Repos/` et `Astuces/`). Ajoute au rapport :
- le nombre de repos et d'astuces écrits dans le vault ;
- les correspondances `a-verifier` (lister `data/resolved/*.json` dont `confidence` vaut `a-verifier`) et les dépôts `non-resolu`, pour que l'utilisateur tranche.
Pré-requis : `gh auth status` OK. Si `VAULT_VEILLE_DIR` n'est pas défini, le signaler.

## Règles
- Ne jamais modifier `data/raw/` ou `data/enriched/` à la main.
- Le pipeline est **idempotent** : une reprise ne retraite que les nouveaux posts (cache par shortcode).
- L'analyse passe par l'**abonnement Claude Code** (aucune clé API à fournir).
- Si l'utilisateur ne précise pas de contexte, passer une chaîne vide.
- Ne jamais commit ni push automatiquement — la skill traite des données, pas du versioning.
