from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

from rich.console import Console

from .profiles import get as get_profile

console = Console()

SENTINEL_NAME = ".enriched.done"


class SentinelError(RuntimeError):
    pass


def _profile_block(profile_name: str, trip_context: str) -> str:
    profile = get_profile(profile_name)
    return (
        f"Profile: {profile.name} — {profile.description}.\n"
        f"Domain-specific instruction:\n{profile.llm_instruction}\n"
        f"User context: {trip_context or '(none)'}.\n"
    )


def _build_prompt(trip_context: str, profile_name: str = "voyage") -> str:
    return (
        "Invoke the skill instatrip-analyze for the current project. "
        + _profile_block(profile_name, trip_context)
        + "Process all data/raw/*.json, write data/enriched/<shortcode>.json "
        "for each, then write the sentinel data/.enriched.done with the stats JSON "
        "as described in the skill. Do not stop before writing the sentinel."
    )


def _build_worker_prompt(
    trip_context: str, worker_id: int, shortcodes: list[str], profile_name: str = "voyage"
) -> str:
    return (
        "Invoke the skill instatrip-analyze for the current project. "
        + _profile_block(profile_name, trip_context)
        + f"Worker ID: {worker_id}. "
        f"Shortcodes à traiter (seulement ceux-là) : {', '.join(shortcodes)}.\n"
        "Pour chaque shortcode listé, lire data/raw/<shortcode>.json et "
        "écrire data/enriched/<shortcode>.json. "
        f"À la fin, écrire la sentinelle data/.enriched.done.{worker_id} "
        "avec les stats JSON décrites dans le skill. Ne pas s'arrêter avant "
        "d'avoir écrit la sentinelle."
    )


def run_analysis(
    collection_root: Path | None = None,
    trip_context: str = "",
    n_workers: int = 1,
    timeout_seconds: int = 60 * 60,
    profile_name: str = "voyage",
    project_root: Path | None = None,
) -> dict:
    """Spawn `claude -p` en headless avec le skill instatrip-analyze.

    - collection_root : dossier qui contient `data/` (typiquement `collections/<slug>/`).
      Le subprocess `claude -p` est lancé avec cwd = collection_root.
    - n_workers=1 (défaut) : un seul process, sentinelle `data/.enriched.done`.
    - n_workers>1 : split des raw JSONs en N buckets, N process parallèles,
      sentinelles `data/.enriched.done.<wid>`, stats agrégées.
    - profile_name : profil d'analyse (voyage / recettes / sport / ...).
    - project_root : alias backward-compat de collection_root (deprecated).
    """
    root = collection_root or project_root
    if root is None:
        raise ValueError("collection_root requis")
    if n_workers <= 1:
        return _run_single(
            root, timeout_seconds, _build_prompt(trip_context, profile_name),
            SENTINEL_NAME, "instatrip-analyze",
        )
    return _run_parallel(
        root, n_workers, timeout_seconds,
        lambda wid, bucket: _build_worker_prompt(trip_context, wid, bucket, profile_name),
        SENTINEL_NAME,
    )


def _run_single(
    collection_root: Path, timeout_seconds: int, prompt: str, sentinel_name: str, skill: str
) -> dict:
    sentinel = collection_root / "data" / sentinel_name
    if sentinel.exists():
        sentinel.unlink()

    console.print(f"[cyan]→ claude -p (skill {skill})")
    subprocess.run(
        ["claude", "-p", prompt],
        cwd=str(collection_root),
        timeout=timeout_seconds,
        check=False,
    )

    if not sentinel.exists():
        raise SentinelError(
            f"Sentinelle absente après exécution : {sentinel}. "
            "Le skill n'a pas fini correctement."
        )
    payload = json.loads(sentinel.read_text(encoding="utf-8-sig"))
    sentinel.unlink()
    if payload.get("status") != "ok":
        raise SentinelError(payload.get("error", "status non-ok"))
    console.print(
        f"[green]✓ analyse OK — processed={payload.get('processed')} "
        f"skipped={payload.get('skipped')} failed={payload.get('failed')}"
    )
    return payload


def _run_parallel(
    collection_root: Path,
    n_workers: int,
    timeout_seconds: int,
    worker_prompt: Callable[[int, list[str]], str],
    sentinel_name: str,
    items_dir: str = "raw",
) -> dict:
    src_dir = collection_root / "data" / items_dir
    shortcodes = sorted(f.stem for f in src_dir.glob("*.json"))
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
        s = collection_root / "data" / f"{sentinel_name}.{wid}"
        if s.exists():
            s.unlink()

    console.print(
        f"[cyan]→ spawn {len(buckets)} workers claude -p "
        f"(buckets: {[len(b) for b in buckets]})"
    )
    procs: list[subprocess.Popen] = []
    for wid, bucket in enumerate(buckets):
        prompt = worker_prompt(wid, bucket)
        p = subprocess.Popen(
            ["claude", "-p", prompt],
            cwd=str(collection_root),
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
    ok_workers = 0
    for wid in range(len(buckets)):
        s = collection_root / "data" / f"{sentinel_name}.{wid}"
        if not s.exists():
            aggregated["failures"].append({"worker": wid, "error": "sentinelle absente"})
            aggregated["failed"] += 1
            continue
        try:
            payload = json.loads(s.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            aggregated["failures"].append({"worker": wid, "error": f"sentinelle illisible: {e}"})
            aggregated["failed"] += 1
            s.unlink()
            continue
        s.unlink()
        if payload.get("status") != "ok":
            aggregated["failures"].append({"worker": wid, "error": payload.get("error", "status non-ok")})
            aggregated["failed"] += 1
            continue
        ok_workers += 1
        aggregated["processed"] += payload.get("processed", 0)
        aggregated["skipped"] += payload.get("skipped", 0)
        aggregated["failed"] += payload.get("failed", 0)
        aggregated["failures"].extend(payload.get("failures", []))

    if ok_workers == 0:
        raise SentinelError(
            f"Tous les workers ont échoué : {aggregated['failures']}"
        )

    console.print(
        f"[green]✓ analyse parallèle OK — processed={aggregated['processed']} "
        f"skipped={aggregated['skipped']} failed={aggregated['failed']}"
    )
    return aggregated


VEILLE_SENTINEL = ".veille.done"


def _veille_prompt(context: str, worker_id: int | None, shortcodes: list[str] | None) -> str:
    scope = (
        f"Worker ID: {worker_id}. Shortcodes à traiter (seulement ceux-là) : {', '.join(shortcodes)}.\n"
        f"Sentinelle de fin : data/{VEILLE_SENTINEL}.{worker_id}.\n"
        if worker_id is not None
        else f"Traiter tous les data/enriched/*.json. Sentinelle de fin : data/{VEILLE_SENTINEL}.\n"
    )
    return (
        "Invoke the skill instatrip-veille for the current project.\n"
        f"Lecteur de la veille : {context or '(non précisé)'}.\n"
        + scope
        + "Ne pas s'arrêter avant d'avoir écrit la sentinelle."
    )


def run_veille(
    collection_root: Path, context: str = "", n_workers: int = 4, timeout_seconds: int = 60 * 60
) -> dict:
    """Phase veille (profil tech) : data/veille/<shortcode>.json par post."""
    if n_workers <= 1:
        return _run_single(
            collection_root, timeout_seconds, _veille_prompt(context, None, None),
            VEILLE_SENTINEL, "instatrip-veille",
        )
    return _run_parallel(
        collection_root, n_workers, timeout_seconds,
        lambda wid, bucket: _veille_prompt(context, wid, bucket),
        VEILLE_SENTINEL, items_dir="enriched",
    )
