from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .session import check_session

_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}


@dataclass
class Check:
    name: str
    status: str          # "ok" | "warn" | "ko"
    blocking: bool
    hint: str
    detail: str = ""


def _cmd_ok(args: list[str]) -> bool:
    try:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def check_ffmpeg() -> Check:
    ok = shutil.which("ffmpeg") is not None
    return Check("ffmpeg", "ok" if ok else "ko", True,
                 "winget install Gyan.FFmpeg")


def check_claude() -> Check:
    ok = _cmd_ok(["claude", "--version"])
    return Check("CLI claude", "ok" if ok else "ko", True,
                 "Installer Claude Code CLI")


def check_chromium() -> Check:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            path = pw.chromium.executable_path
            ok = bool(path) and Path(path).exists()
    except Exception:
        ok = False
    return Check("Chromium Playwright", "ok" if ok else "ko", True,
                 "uv run playwright install chromium")


def check_torch() -> Check:
    try:
        import torch
        cuda = torch.cuda.is_available()
        return Check("torch / CUDA", "ok" if cuda else "warn", False,
                     "uv sync (CUDA optionnel — fallback CPU)",
                     detail="CUDA actif" if cuda else "CPU uniquement")
    except Exception:
        return Check("torch / CUDA", "warn", False, "uv sync", detail="torch absent")


def check_ig_session(state_path: Path) -> Check:
    res = check_session(state_path)
    status_map = {"fresh": "ok", "expiring": "warn", "expired": "ko", "missing": "ko"}
    status = status_map.get(res["status"], "ko")
    detail = res["status"]
    if res.get("days_left") is not None:
        detail = f"{res['status']} ({res['days_left']:.0f} j restants)"
    return Check("Session IG", status, status == "ko",
                 "uv run instatrip auth", detail=detail)


def check_teams_videos(base_path: Path | None = None) -> Check:
    """Non-blocking informational check: are there any videos in collections/*/input/?"""
    if base_path is None:
        base_path = Path.cwd()
    collections_root = base_path / "collections"
    found: list[str] = []
    if collections_root.exists():
        for input_dir in collections_root.glob("*/input"):
            if input_dir.is_dir():
                slug = input_dir.parent.name
                videos = [f for f in input_dir.iterdir()
                          if f.is_file() and f.suffix.lower() in _VIDEO_EXTS]
                if videos:
                    found.append(f"{slug} ({len(videos)} vidéo{'s' if len(videos) > 1 else ''})")
    if found:
        return Check(
            name="Teams videos",
            status="ok",
            blocking=False,
            hint="",
            detail=f"Vidéo(s) détectée(s) : {', '.join(found)}",
        )
    return Check(
        name="Teams videos",
        status="warn",
        blocking=False,
        hint="Dépose une vidéo dans collections/<slug>/input/ pour le mode Teams.",
        detail="Aucune vidéo détectée",
    )


def build_report(state_path: Path) -> list[Check]:
    return [
        check_ffmpeg(),
        check_claude(),
        check_chromium(),
        check_torch(),
        check_ig_session(state_path),
        check_teams_videos(state_path.parent),
    ]


def has_blocking_failure(report: list[Check]) -> bool:
    return any(c.blocking and c.status == "ko" for c in report)
