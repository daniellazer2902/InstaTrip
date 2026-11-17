from __future__ import annotations

from . import Profile, register

INSTRUCTION = """\
Domaine : veille technique à partir de reels Instagram (repos GitHub, outils de dev, astuces IA, prompts).

Catégories possibles (champ `category`) :
- `repo` : le post présente un ou plusieurs dépôts GitHub/GitLab précis
- `outil` : le post présente un outil, une app, un SaaS ou une extension (sans dépôt identifiable)
- `tip-ia` : astuce d'usage d'un assistant IA, d'un agent, d'un workflow IA
- `prompt` : le post donne un prompt réutilisable (le recopier dans `description` si lisible)
- `tuto` : tutoriel ou explication technique générale
- `autre` : post non exploitable

Champs à remplir dans `attributes` :
- `repos` : liste des dépôts cités. Format `owner/nom` si l'owner est lisible (OCR, URL github.com/..., légende),
  sinon le nom seul tel qu'il apparaît. Sources à fouiller : `ocr_text` (le nom est souvent affiché
  à l'écran), `transcript` (le nom est souvent prononcé, parfois déformé par la transcription : garder
  la graphie la plus plausible), `caption`, `pinned_comment`. Liste vide si aucun.
- `outils` : liste des outils / produits / librairies cités (noms propres, sans doublon avec `repos`).
- `stack` : liste de technologies concernées (ex: `python`, `react`, `claude-code`, `mcp`, `docker`).
- `cas_usage` : une phrase courte, à quoi ça sert concrètement pour un dev.
- `mot_cle_cta` : si le post demande de commenter un mot pour recevoir le lien
  (« commente REPO », « tape GITHUB »...), le mot demandé, sinon null.

Règles :
- Ne JAMAIS inventer un nom de dépôt ou d'owner absent des données.
- Un même nom vu en OCR et entendu dans la transcription : privilégier la graphie OCR.
- Tags : 2-5 mots-clés courts en kebab-case (ex: `agent-ia`, `self-hosted`, `productivite`, `scraping`).
"""


BASE_TEMPLATE = """\
filters:
  and:
    - 'shortcode != ""'

formulas:
  ig_link: 'if(url, link(url, "↗ IG"), "")'

properties:
  title:
    displayName: Titre
  category:
    displayName: Catégorie
  repos:
    displayName: Repos
  stack:
    displayName: Stack
  cas_usage:
    displayName: Cas d'usage
  formula.ig_link:
    displayName: Lien

views:
  - type: table
    name: "Tout"
    order: [title, category, repos, stack, cas_usage, formula.ig_link]

  - type: table
    name: "Repos"
    filters:
      and: ['category == "repo"']
    order: [title, repos, stack, cas_usage, formula.ig_link]

  - type: table
    name: "Tips IA et prompts"
    filters:
      or: ['category == "tip-ia"', 'category == "prompt"']
    order: [title, outils, cas_usage, formula.ig_link]
"""


register(Profile(
    name="tech",
    description="Veille technique (repos GitHub, outils, astuces IA, prompts) à partir de reels",
    categories=["repo", "outil", "tip-ia", "prompt", "tuto", "autre"],
    attribute_fields=[
        ("repos", "Repos"),
        ("outils", "Outils"),
        ("stack", "Stack"),
        ("cas_usage", "Cas d'usage"),
        ("mot_cle_cta", "Mot-clé CTA"),
    ],
    llm_instruction=INSTRUCTION,
    base_template=BASE_TEMPLATE,
))
