from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import httpx
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


def download_video(shortcode: str, state_path: Path, media_dir: Path) -> Optional[Path]:
    """Télécharge la vidéo d'un reel via yt-dlp (format vidéo uniquement)."""
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
        ydl.extract_info(url, download=True)

    for f in media_dir.glob(f"{shortcode}.*"):
        if f.suffix.lower() in {".mp4", ".mov", ".webm"}:
            return f
    return None


def download_images(image_urls: list[str], media_dir: Path, shortcode: str) -> list[Path]:
    """Télécharge les bytes des images d'un post photo/carrousel via HTTP."""
    media_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for i, url in enumerate(image_urls):
            r = client.get(url)
            r.raise_for_status()
            p = media_dir / f"{shortcode}_{i}.jpg"
            p.write_bytes(r.content)
            paths.append(p)
    return paths


def download_media(
    shortcode: str,
    state_path: Path,
    media_dir: Path,
    is_video: bool,
    image_urls: Optional[list[str]] = None,
) -> dict:
    """Orchestrateur : vidéo → yt-dlp, sinon téléchargement HTTP des images.
    Plus aucun appel yt-dlp pour les posts photo (fini le crash
    'No video formats found')."""
    if is_video:
        video_path = download_video(shortcode, state_path, media_dir)
        return {"video_path": video_path, "image_paths": [], "media_type": "reel"}
    paths = download_images(image_urls or [], media_dir, shortcode)
    return {
        "video_path": None,
        "image_paths": paths,
        "media_type": "carousel" if len(paths) > 1 else "image",
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


def _dhash_grid(pixels: list[int]) -> int:
    """Convertit 9×8 pixels (grayscale) en hash dHash 64 bits."""
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            if left > right:
                bits |= (1 << (row * 8 + col))
    return bits


def _dhash(image_path: Path) -> int:
    """Perceptual hash 8×8 sur l'image entière (mode 'full')."""
    from PIL import Image

    img = Image.open(image_path).convert("L").resize((9, 8), Image.LANCZOS)
    return _dhash_grid(list(img.getdata()))


def _dhash_bands(image_path: Path, band_ratio: float = 0.3) -> tuple[int, int]:
    """Deux hashes : bande haute (top band_ratio) + bande basse (bottom
    band_ratio). Cible les zones d'overlays texte sur les reels IG."""
    from PIL import Image

    img = Image.open(image_path).convert("L")
    w, h = img.size
    band_h = max(1, int(h * band_ratio))
    top_img = img.crop((0, 0, w, band_h)).resize((9, 8), Image.LANCZOS)
    bot_img = img.crop((0, h - band_h, w, h)).resize((9, 8), Image.LANCZOS)
    return _dhash_grid(list(top_img.getdata())), _dhash_grid(list(bot_img.getdata()))


def dedup_frames(
    paths: list[Path],
    threshold: int = 6,
    mode: str = "bands",
) -> list[Path]:
    """Garde une frame par 'plan' visuel.

    - mode='full' : un hash 64-bit sur toute l'image. Skip si Hamming ≤ threshold.
    - mode='bands' (défaut) : hash séparé sur bande haute (30%) + bande basse
      (30%) — cible les overlays texte des reels. La frame est gardée si
      l'une OU l'autre bande dépasse le seuil.

    threshold=6 = bon compromis : capte les overlays texte qui changent,
    skip les frames quasi-identiques d'un plan fixe sans texte."""
    if mode not in {"full", "bands"}:
        raise ValueError(f"mode must be 'full' or 'bands', got {mode!r}")

    kept: list[Path] = []
    last_hash: int | tuple[int, int] | None = None
    for p in paths:
        if mode == "full":
            h = _dhash(p)
            if last_hash is None or bin(h ^ last_hash).count("1") > threshold:
                kept.append(p)
                last_hash = h
        else:
            h_top, h_bot = _dhash_bands(p)
            if last_hash is None:
                kept.append(p)
                last_hash = (h_top, h_bot)
                continue
            top_dist = bin(h_top ^ last_hash[0]).count("1")
            bot_dist = bin(h_bot ^ last_hash[1]).count("1")
            if top_dist > threshold or bot_dist > threshold:
                kept.append(p)
                last_hash = (h_top, h_bot)
    return kept
