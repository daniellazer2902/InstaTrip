"""Profils de collection — chaque profil définit le domaine d'analyse
(voyage, recettes, sport, ...), son prompt LLM, son template Obsidian Base,
et les champs spécifiques à extraire."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    categories: list[str]
    attribute_fields: list[tuple[str, str]]
    llm_instruction: str
    base_template: str


PROFILES: dict[str, Profile] = {}


def register(profile: Profile) -> None:
    PROFILES[profile.name] = profile


def get(name: str) -> Profile:
    if name not in PROFILES:
        available = ", ".join(sorted(PROFILES))
        raise KeyError(f"Profile '{name}' inconnu. Disponibles : {available}")
    return PROFILES[name]


def all_names() -> list[str]:
    return sorted(PROFILES.keys())


from . import voyage as _voyage  # noqa: E402, F401
from . import recettes as _recettes  # noqa: E402, F401
from . import sport as _sport  # noqa: E402, F401
from . import tech as _tech  # noqa: E402, F401
