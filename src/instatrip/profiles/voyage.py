from __future__ import annotations

from . import Profile, register

INSTRUCTION = """\
Domaine : préparation d'un voyage à partir de posts Instagram (reels travel).

Catégories possibles (champ `category`) :
- `lieu` : restaurant, hôtel, point d'intérêt précis (un seul endroit identifiable)
- `tips` : conseil général non lié à un lieu unique (apps, logistique, langue)
- `activite` : expérience ou activité à faire (atelier, randonnée, expérience locale)
- `autre` : post non exploitable

Champs à remplir (top-level dans le JSON enrichi) :
- `city` : ville mentionnée si claire, sinon null. Ne JAMAIS inventer.
- `neighborhood` : quartier/secteur si explicite, sinon null.
- `activity` : libellé court de l'activité (verbe d'action), sinon null.

Tags : 2-5 mots-clés courts en kebab-case français (ex: `ramen`, `vue-panoramique`, `petit-dejeuner`).
"""


BASE_TEMPLATE = """\
filters:
  and:
    - 'shortcode != ""'

formulas:
  cat_icon: 'if(category == "lieu", "📍", if(category == "tips", "💡", if(category == "activite", "🎯", "📝")))'
  ig_link: 'if(url, link(url, "↗ IG"), "")'

properties:
  formula.cat_icon:
    displayName: ""
  title:
    displayName: Titre
  category:
    displayName: Catégorie
  city:
    displayName: Ville
  neighborhood:
    displayName: Quartier
  formula.ig_link:
    displayName: Lien

views:
  - type: cards
    name: "🗾 Tout"
    order: [formula.cat_icon, title, city, neighborhood]

  - type: table
    name: "📍 Lieux"
    filters:
      and: ['category == "lieu"']
    groupBy: { property: city, direction: ASC }
    order: [title, neighborhood, formula.ig_link]

  - type: table
    name: "💡 Tips"
    filters:
      and: ['category == "tips"']
    order: [title, city, formula.ig_link]

  - type: table
    name: "🎯 Activités"
    filters:
      and: ['category == "activite"']
    groupBy: { property: city, direction: ASC }
    order: [title, neighborhood, formula.ig_link]

  - type: table
    name: "🗼 Tokyo"
    filters:
      and: ['city == "Tokyo"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "🏯 Osaka"
    filters:
      and: ['city == "Osaka"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "⛩️ Kyoto"
    filters:
      and: ['city == "Kyoto"']
    groupBy: { property: neighborhood, direction: ASC }
    order: [formula.cat_icon, title, formula.ig_link]

  - type: table
    name: "🗺️ Autres villes"
    filters:
      and:
        - 'city != ""'
        - 'city != "Tokyo"'
        - 'city != "Osaka"'
        - 'city != "Kyoto"'
    groupBy: { property: city, direction: ASC }
    order: [formula.cat_icon, title, neighborhood, formula.ig_link]
"""


register(Profile(
    name="voyage",
    description="Préparation de voyage (lieux, tips, activités) à partir de reels travel",
    categories=["lieu", "tips", "activite", "autre"],
    attribute_fields=[
        ("city", "Ville"),
        ("neighborhood", "Quartier"),
        ("activity", "Activité"),
    ],
    llm_instruction=INSTRUCTION,
    base_template=BASE_TEMPLATE,
))
