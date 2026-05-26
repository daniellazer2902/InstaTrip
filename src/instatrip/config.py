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
    project_root: Path
    raw_dir: Path
    enriched_dir: Path
    media_dir: Path
    output_dir: Path
    obsidian_dir: Path
    state_path: Path

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        root = Path.cwd()
        raw = root / "data" / "raw"
        enriched = root / "data" / "enriched"
        media = root / "data" / "media"
        output = root / "output"
        obsidian = output / "obsidian"
        secrets = root / ".secrets"
        for p in (raw, enriched, media, output, obsidian, secrets):
            p.mkdir(parents=True, exist_ok=True)
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            collection_url=os.environ.get("COLLECTION_URL", ""),
            collection_slug=os.environ.get("COLLECTION_SLUG", "collection"),
            project_root=root,
            raw_dir=raw,
            enriched_dir=enriched,
            media_dir=media,
            output_dir=output,
            obsidian_dir=obsidian,
            state_path=secrets / "ig_state.json",
        )
