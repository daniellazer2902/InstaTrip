from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

SENTINEL_NAME = ".enriched.done"


class SentinelError(RuntimeError):
    pass


def _build_prompt(trip_context: str) -> str:
    return (
        "Invoke the skill instatrip-analyze for the current project. "
        f"Trip context: {trip_context or '(none)'}.\n"
        "Process all data/raw/*.json, write data/enriched/<shortcode>.json "
        "for each, then write the sentinel data/.enriched.done with the stats JSON "
        "as described in the skill. Do not stop before writing the sentinel."
    )


def run_analysis(
    project_root: Path,
    trip_context: str = "",
    timeout_seconds: int = 60 * 60,
) -> dict:
    """Spawn `claude -p` en headless avec le prompt qui invoque le skill
    instatrip-analyze. Attend la sentinelle, la lit, la supprime, la retourne."""
    sentinel = project_root / "data" / SENTINEL_NAME
    prompt = _build_prompt(trip_context)
    console.print(f"[cyan]→ claude -p (skill instatrip-analyze)")
    subprocess.run(
        ["claude", "-p", prompt],
        cwd=str(project_root),
        timeout=timeout_seconds,
        check=False,
    )

    if not sentinel.exists():
        raise SentinelError(
            f"Sentinelle absente après exécution : {sentinel}. "
            "Le skill n'a pas fini correctement."
        )
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    sentinel.unlink()
    if payload.get("status") != "ok":
        raise SentinelError(payload.get("error", "status non-ok"))
    console.print(
        f"[green]✓ analyse OK — processed={payload.get('processed')} "
        f"skipped={payload.get('skipped')} failed={payload.get('failed')}"
    )
    return payload
