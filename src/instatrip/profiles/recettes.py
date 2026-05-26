from __future__ import annotations

from . import Profile, register

INSTRUCTION = """\
Domaine : recettes de cuisine à partir de posts Instagram (vidéos/photos food).

Catégories possibles (champ `category`) :
- `plat` : recette de plat principal
- `dessert` : recette sucrée, pâtisserie, boisson sucrée
- `boisson` : cocktail, smoothie, boisson chaude
- `technique` : technique de cuisine, astuce de préparation, équipement
- `ingredient` : focus sur un ingrédient (origine, sélection, utilisation)
- `autre` : non exploitable

Champs à remplir dans `attributes` (dictionnaire) :
- `cuisine` : origine culinaire (japonaise, italienne, française, fusion…) si claire
- `difficulte` : facile, moyen, difficile (si évoquée)
- `temps` : durée de préparation (ex: "30 min", "1h") si mentionnée
- `ingredients_cles` : liste-string des 3-5 ingrédients principaux séparés par virgule

Tags : 3-5 mots-clés courts en kebab-case français (ex: `sans-gluten`, `vegetarien`, `batch-cooking`, `kawaii`, `street-food`).
"""


BASE_TEMPLATE = """\
filters:
  and:
    - 'shortcode != ""'

formulas:
  cat_icon: 'if(category == "plat", "🍽️", if(category == "dessert", "🍰", if(category == "boisson", "🍹", if(category == "technique", "🔪", if(category == "ingredient", "🥕", "📝")))))'
  ig_link: 'if(url, link(url, "↗ IG"), "")'

properties:
  formula.cat_icon:
    displayName: ""
  title:
    displayName: Titre
  category:
    displayName: Catégorie
  cuisine:
    displayName: Cuisine
  difficulte:
    displayName: Difficulté
  temps:
    displayName: Temps
  ingredients_cles:
    displayName: Ingrédients
  formula.ig_link:
    displayName: Lien

views:
  - type: cards
    name: "🍽️ Tout"
    order: [formula.cat_icon, title, cuisine, temps]

  - type: table
    name: "🍽️ Plats"
    filters:
      and: ['category == "plat"']
    groupBy: { property: cuisine, direction: ASC }
    order: [title, difficulte, temps, ingredients_cles, formula.ig_link]

  - type: table
    name: "🍰 Desserts"
    filters:
      and: ['category == "dessert"']
    order: [title, cuisine, temps, ingredients_cles, formula.ig_link]

  - type: table
    name: "🍹 Boissons"
    filters:
      and: ['category == "boisson"']
    order: [title, cuisine, ingredients_cles, formula.ig_link]

  - type: table
    name: "🔪 Techniques"
    filters:
      and: ['category == "technique"']
    order: [title, cuisine, formula.ig_link]

  - type: table
    name: "⚡ Rapides (≤ 30 min)"
    filters:
      and:
        - 'temps != ""'
        - 'temps.contains("min")'
    order: [title, category, temps, difficulte, formula.ig_link]

  - type: table
    name: "🥇 Faciles"
    filters:
      and: ['difficulte == "facile"']
    order: [title, category, cuisine, temps, formula.ig_link]
"""


register(Profile(
    name="recettes",
    description="Recettes de cuisine (plats, desserts, techniques) à partir de reels food",
    categories=["plat", "dessert", "boisson", "technique", "ingredient", "autre"],
    attribute_fields=[
        ("cuisine", "Cuisine"),
        ("difficulte", "Difficulté"),
        ("temps", "Temps"),
        ("ingredients_cles", "Ingrédients clés"),
    ],
    llm_instruction=INSTRUCTION,
    base_template=BASE_TEMPLATE,
))
