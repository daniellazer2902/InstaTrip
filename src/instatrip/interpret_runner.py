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


def _build_worker_prompt(trip_context: str, worker_id: int, shortcodes: list[str]) -> str:
    return (
        "Invoke the skill instatrip-analyze for the current project. "
        f"Trip context: {trip_context or '(none)'}. "
        f"Worker ID: {worker_id}. "
        f"Shortcodes à traiter (seulement ceux-là) : {', '.join(shortcodes)}.\n"
        "Pour chaque shortcode listé, lire data/raw/<shortcode>.json et "
        "écrire data/enriched/<shortcode>.json. "
        f"À la fin, écrire la sentinelle data/.enriched.done.{worker_id} "
        "avec les stats JSON décrites dans le skill. Ne pas s'arrêter avant "
        "d'avoir écrit la sentinelle."
    )


def run_analysis(
    project_root: Path,
    trip_context: str = "",
    n_workers: int = 1,
    timeout_seconds: int = 60 * 60,
) -> dict:
    """Spawn `claude -p` en headless avec le skill instatrip-analyze.

    - n_workers=1 (défaut) : un seul process, sentinelle `data/.enriched.done`.
    - n_workers>1 : split des raw JSONs en N buckets, N process parallèles,
      sentinelles `data/.enriched.done.<wid>`, stats agrégées.
    """
    if n_workers <= 1:
        return _run_single(project_root, trip_context, timeout_seconds)
    return _run_parallel(project_root, trip_context, n_workers, timeout_seconds)


def _run_single(project_root: Path, trip_context: str, timeout_seconds: int) -> dict:
    sentinel = project_root / "data" / SENTINEL_NAME
    if sentinel.exists():
        sentinel.unlink()

    prompt = _build_prompt(trip_context)
    console.print("[cyan]→ claude -p (skill instatrip-analyze)")
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


def _run_parallel(
    project_root: Path, trip_context: str, n_workers: int, timeout_seconds: int
) -> dict:
    raw_dir = project_root / "data" / "raw"
    shortcodes = sorted(f.stem for f in raw_dir.glob("*.json"))
    if not shortcodes:
        return {
            "status": "ok",
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "failures": [],
        }

    buckets = [shortcodes[i::n_workers] for i in range(n_workers)]
    buckets = [b for b in buckets if b]

    for wid in range(len(buckets)):
        s = project_root / "data" / f"{SENTINEL_NAME}.{wid}"
        if s.exists():
            s.unlink()

    console.print(
        f"[cyan]→ spawn {len(buckets)} workers claude -p "
        f"(buckets: {[len(b) for b in buckets]})"
    )
    procs: list[subprocess.Popen] = []
    for wid, bucket in enumerate(buckets):
        prompt = _build_worker_prompt(trip_context, wid, bucket)
        p = subprocess.Popen(
            ["claude", "-p", prompt],
            cwd=str(project_root),
        )
        procs.append(p)

    for wid, p in enumerate(procs):
        try:
            p.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            p.kill()
            raise SentinelError(f"Worker {wid} timeout après {timeout_seconds}s")

    aggregated = {
        "status": "ok",
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }
    for wid in range(len(buckets)):
        s = project_root / "data" / f"{SENTINEL_NAME}.{wid}"
        if not s.exists():
            raise SentinelError(f"Sentinelle worker {wid} absente : {s}")
        payload = json.loads(s.read_text(encoding="utf-8"))
        s.unlink()
        if payload.get("status") != "ok":
            raise SentinelError(
                f"Worker {wid} : {payload.get('error', 'status non-ok')}"
            )
        aggregated["processed"] += payload.get("processed", 0)
        aggregated["skipped"] += payload.get("skipped", 0)
        aggregated["failed"] += payload.get("failed", 0)
        aggregated["failures"].extend(payload.get("failures", []))

    console.print(
        f"[green]✓ analyse parallèle OK — processed={aggregated['processed']} "
        f"skipped={aggregated['skipped']} failed={aggregated['failed']}"
    )
    return aggregated
