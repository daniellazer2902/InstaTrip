from __future__ import annotations

from pathlib import Path


def scaffold_collection(project_root: Path, slug: str, url: str, profile: str = "voyage") -> Path:
    """Crée collections/<slug>/ + .env. Refuse si le .env existe déjà."""
    col = project_root / "collections" / slug
    env = col / ".env"
    if env.exists():
        raise FileExistsError(
            f"La collection '{slug}' existe déjà ({env}). Utilise la reprise."
        )
    (col / "data").mkdir(parents=True, exist_ok=True)
    env.write_text(
        f"COLLECTION_URL={url}\n"
        f"COLLECTION_SLUG={slug}\n"
        f"COLLECTION_PROFILE={profile}\n",
        encoding="utf-8",
    )
    return env
