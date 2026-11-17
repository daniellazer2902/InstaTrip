from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    anthropic_model: str
    collection_url: str
    collection_slug: str
    collection_profile: str
    project_root: Path
    collection_root: Path
    raw_dir: Path
    enriched_dir: Path
    media_dir: Path
    output_dir: Path
    obsidian_dir: Path
    state_path: Path
    shortcodes_file: Path
    input_dir: Path
    resolved_dir: Path | None = None
    vault_veille_dir: Path | None = None

    @classmethod
    def load(cls, collection: str | None = None) -> "Settings":
        """Charge les settings pour une collection donnée.

        - `collection` : slug de la collection (sous-dossier `collections/<slug>/`).
          Si None, lu depuis l'env var `COLLECTION_SLUG`.
        - Une .env optionnelle dans `collections/<slug>/.env` override la `.env` racine.
        """
        load_dotenv()
        project_root = Path.cwd()

        slug = collection or os.environ.get("COLLECTION_SLUG", "collection")
        collection_root = project_root / "collections" / slug

        # .env de collection optionnelle (override la racine)
        col_env = collection_root / ".env"
        if col_env.exists():
            load_dotenv(col_env, override=True)

        raw = collection_root / "data" / "raw"
        enriched = collection_root / "data" / "enriched"
        media = collection_root / "data" / "media"
        output = collection_root / "output"
        obsidian = output / "obsidian"
        secrets = project_root / ".secrets"
        shortcodes_file = collection_root / "data" / "shortcodes.json"
        input_dir = collection_root / "input"

        for p in (raw, enriched, media, output, obsidian, secrets, input_dir):
            p.mkdir(parents=True, exist_ok=True)

        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            collection_url=os.environ.get("COLLECTION_URL", ""),
            collection_slug=slug,
            collection_profile=os.environ.get("COLLECTION_PROFILE", "voyage"),
            project_root=project_root,
            collection_root=collection_root,
            raw_dir=raw,
            enriched_dir=enriched,
            media_dir=media,
            output_dir=output,
            obsidian_dir=obsidian,
            state_path=secrets / "ig_state.json",
            shortcodes_file=shortcodes_file,
            input_dir=input_dir,
            resolved_dir=collection_root / "data" / "resolved",
            vault_veille_dir=Path(v) if (v := os.environ.get("VAULT_VEILLE_DIR")) else None,
        )
