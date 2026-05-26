from __future__ import annotations

from . import Profile, register

INSTRUCTION = """\
Domaine : exercices de sport et entraînement à partir de posts Instagram (reels fitness/sport).

Catégories possibles (champ `category`) :
- `cardio` : course, vélo, HIIT, conditionnement aérobie
- `musculation` : renforcement, poids, hypertrophie, force
- `mobilite` : étirements, yoga, souplesse, fascia
- `technique` : tutoriel d'exécution, posture, correction
- `programme` : routine complète, programme hebdo, conseil structuration
- `autre` : non exploitable

Champs à remplir dans `attributes` (dictionnaire) :
- `groupe_musculaire` : zone ciblée principale (jambes, dos, pectoraux, full-body, core...) si claire
- `equipement` : matériel requis (haltères, élastiques, barre, poids du corps, machine, kettlebell...) si mentionné
- `niveau` : débutant, intermédiaire, avancé (si évoqué)
- `duree` : durée de l'exercice/séance (ex: "10 min", "45 min", "3 séries x 12") si mentionnée

Tags : 3-5 mots-clés courts en kebab-case français (ex: `hiit`, `poids-corps`, `home-gym`, `prise-de-masse`, `recuperation`).
"""


BASE_TEMPLATE = """\
filters:
  and:
    - 'shortcode != ""'

formulas:
  cat_icon: 'if(category == "cardio", "🏃", if(category == "musculation", "🏋️", if(category == "mobilite", "🧘", if(category == "technique", "🎯", if(category == "programme", "📋", "📝")))))'
  ig_link: 'if(url, link(url, "↗ IG"), "")'

properties:
  formula.cat_icon:
    displayName: ""
  title:
    displayName: Titre
  category:
    displayName: Catégorie
  groupe_musculaire:
    displayName: Zone
  equipement:
    displayName: Matériel
  niveau:
    displayName: Niveau
  duree:
    displayName: Durée
  formula.ig_link:
    displayName: Lien

views:
  - type: cards
    name: "💪 Tout"
    order: [formula.cat_icon, title, groupe_musculaire, equipement]

  - type: table
    name: "🏋️ Musculation"
    filters:
      and: ['category == "musculation"']
    groupBy: { property: groupe_musculaire, direction: ASC }
    order: [title, equipement, niveau, duree, formula.ig_link]

  - type: table
    name: "🏃 Cardio"
    filters:
      and: ['category == "cardio"']
    order: [title, duree, niveau, equipement, formula.ig_link]

  - type: table
    name: "🧘 Mobilité"
    filters:
      and: ['category == "mobilite"']
    groupBy: { property: groupe_musculaire, direction: ASC }
    order: [title, duree, formula.ig_link]

  - type: table
    name: "🎯 Techniques"
    filters:
      and: ['category == "technique"']
    groupBy: { property: groupe_musculaire, direction: ASC }
    order: [title, equipement, formula.ig_link]

  - type: table
    name: "📋 Programmes"
    filters:
      and: ['category == "programme"']
    order: [title, niveau, duree, formula.ig_link]

  - type: table
    name: "🏠 Sans matériel"
    filters:
      or:
        - 'equipement == ""'
        - 'equipement.contains("poids du corps")'
        - 'equipement.contains("aucun")'
    order: [title, category, groupe_musculaire, formula.ig_link]
"""


register(Profile(
    name="sport",
    description="Exercices et entraînement (musculation, cardio, mobilité) à partir de reels fitness",
    categories=["cardio", "musculation", "mobilite", "technique", "programme", "autre"],
    attribute_fields=[
        ("groupe_musculaire", "Groupe musculaire"),
        ("equipement", "Équipement"),
        ("niveau", "Niveau"),
        ("duree", "Durée"),
    ],
    llm_instruction=INSTRUCTION,
    base_template=BASE_TEMPLATE,
))
