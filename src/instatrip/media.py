from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import yt_dlp


def export_cookies_netscape(state_path: Path, out_path: Path) -> None:
    """Convertit un storage_state Playwright en fichier cookies Netscape
    consommable par yt-dlp."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    lines = ["# Netscape HTTP Cookie File"]
    for c in state.get("cookies", []):
        if "instagram.com" not in c.get("domain", ""):
            continue
        domain = c["domain"]
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expiry = int(c.get("expires", 0)) if c.get("expires", -1) > 0 else 0
        name = c["name"]
        value = c["value"]
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def download_media(shortcode: str, state_path: Path, media_dir: Path) -> dict:
    """Télécharge le média du post (vidéo ou image) + métadonnées.
    Retourne {video_path, image_paths, media_type, info_dict}."""
    media_dir.mkdir(parents=True, exist_ok=True)
    cookies = media_dir.parent / ".cookies.txt"
    export_cookies_netscape(state_path, cookies)

    url = f"https://www.instagram.com/p/{shortcode}/"
    out_tpl = str(media_dir / f"{shortcode}.%(ext)s")
    ydl_opts = {
        "outtmpl": out_tpl,
        "cookiefile": str(cookies),
        "quiet": True,
        "no_warnings": True,
        "writeinfojson": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    video_path: Optional[Path] = None
    images: list[Path] = []
    for f in media_dir.glob(f"{shortcode}.*"):
        if f.suffix.lower() in {".mp4", ".mov", ".webm"}:
            video_path = f
        elif f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            images.append(f)
    return {
        "video_path": video_path,
        "image_paths": images,
        "media_type": "reel" if video_path else "image",
        "info": {"title": info.get("title"), "description": info.get("description")},
    }


def extract_audio(video_path: Path, out_wav: Path) -> Path:
    """Extrait l'audio mono 16k via ffmpeg (fourni par yt-dlp)."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-ac", "1", "-ar", "16000",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out_wav


def sample_frames(video_path: Path, out_dir: Path, every_seconds: float = 2.0) -> list[Path]:
    """Échantillonne des frames toutes les N secondes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%03d.jpg")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"fps=1/{every_seconds}",
            "-q:v", "3",
            pattern,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return sorted(out_dir.glob("frame_*.jpg"))


def _dhash(image_path: Path) -> int:
    """Perceptual hash 8×8 sensible aux changements de layout, insensible
    aux variations brightness/contrast."""
    from PIL import Image

    img = Image.open(image_path).convert("L").resize((9, 8), Image.LANCZOS)
    pixels = list(img.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            if left > right:
                bits |= (1 << (row * 8 + col))
    return bits


def dedup_frames(paths: list[Path], threshold: int = 6) -> list[Path]:
    """Garde une frame par 'plan' visuel. Si une frame est trop similaire
    (Hamming distance ≤ threshold) à la dernière retenue, on la skip.
    threshold=6 = bon compromis : capte les overlays de texte courts,
    skip les frames quasi-identiques d'un plan fixe."""
    kept: list[Path] = []
    last_hash: int | None = None
    for p in paths:
        h = _dhash(p)
        if last_hash is None or bin(h ^ last_hash).count("1") > threshold:
            kept.append(p)
            last_hash = h
    return kept
