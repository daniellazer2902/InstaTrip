from __future__ import annotations

import json
import shutil
from pathlib import Path

from rich.console import Console

from .config import Settings
from .media import dedup_frames, download_media, extract_audio, sample_frames
from .models import MediaType, RawPost
from .ocr import ocr_images
from .post_page import fetch_post
from .transcribe import transcribe

console = Console()


def _raw_path(settings: Settings, shortcode: str) -> Path:
    return settings.raw_dir / f"{shortcode}.json"


def extract_one(
    shortcode: str,
    settings: Settings,
    force: bool = False,
    frame_interval: float = 2.0,
    ocr_min_confidence: float = 0.4,
    frame_dedup: bool = True,
    dedup_threshold: int = 6,
    dedup_mode: str = "bands",
) -> RawPost:
    """Pipeline phase 1 pour un post. Idempotent : si le JSON existe
    déjà, on le relit (sauf si force=True).

    - frame_interval : intervalle en secondes entre les frames échantillonnées
      pour l'OCR (défaut 2.0). Plus petit = plus de frames = plus de temps OCR.
    - ocr_min_confidence : seuil de confiance EasyOCR (défaut 0.4).
    - frame_dedup : si True, skip les frames quasi-identiques via dHash.
    - dedup_threshold : Hamming distance maximale pour considérer une frame
      comme doublon (défaut 6, plus bas = plus strict).
    - dedup_mode : 'bands' (défaut, top+bottom 30%) ou 'full' (image entière)."""
    out = _raw_path(settings, shortcode)
    if out.exists() and not force:
        console.print(f"[dim]cache hit: {shortcode}")
        return RawPost.model_validate_json(out.read_text(encoding="utf-8"))

    console.print(f"[cyan]→ {shortcode}: fetch page")
    page = fetch_post(shortcode, settings.state_path)

    console.print(f"[cyan]→ {shortcode}: download media")
    media = download_media(
        shortcode,
        settings.state_path,
        settings.media_dir,
        is_video=page.get("is_video", False),
        image_urls=page.get("image_urls", []),
    )

    transcript: str | None = None
    ocr_text: list[str] = []
    if media["video_path"]:
        wav = settings.media_dir / f"{shortcode}.wav"
        extract_audio(media["video_path"], wav)
        console.print(f"[cyan]→ {shortcode}: transcribe")
        transcript = transcribe(wav)

        frames_dir = settings.media_dir / f"{shortcode}_frames"
        frames = sample_frames(media["video_path"], frames_dir, every_seconds=frame_interval)
        if frame_dedup and frames:
            before = len(frames)
            frames = dedup_frames(frames, threshold=dedup_threshold, mode=dedup_mode)
            console.print(f"[dim]→ {shortcode}: dedup ({dedup_mode}) frames {before} → {len(frames)}")
        if frames:
            console.print(f"[cyan]→ {shortcode}: OCR {len(frames)} frames")
            ocr_text = ocr_images(frames, min_confidence=ocr_min_confidence)
    elif media["image_paths"]:
        console.print(f"[cyan]→ {shortcode}: OCR image(s)")
        ocr_text = ocr_images(media["image_paths"], min_confidence=ocr_min_confidence)

    if media["video_path"]:
        media_type = MediaType.REEL
    elif len(media["image_paths"]) > 1:
        media_type = MediaType.CAROUSEL
    else:
        media_type = MediaType.IMAGE

    post = RawPost(
        shortcode=shortcode,
        url=page["url"],
        media_type=media_type,
        caption=page.get("caption") or "",
        pinned_comment=page.get("pinned_comment"),
        transcript=transcript,
        ocr_text=ocr_text,
        author=page.get("author"),
    )
    out.write_text(post.model_dump_json(indent=2), encoding="utf-8")
    _cleanup_media(settings.media_dir, shortcode)
    console.print(f"[green]✓ {shortcode} saved")
    return post


def _cleanup_media(media_dir: Path, shortcode: str) -> None:
    """Supprime les médias intermédiaires (mp4/wav/jpg/frames) une fois
    le JSON brut écrit. Le JSON reste la source de vérité."""
    for f in media_dir.glob(f"{shortcode}.*"):
        try:
            f.unlink()
        except OSError:
            pass
    frames_dir = media_dir / f"{shortcode}_frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)


def extract_all(
    shortcodes: list[str],
    settings: Settings,
    force: bool = False,
    frame_interval: float = 2.0,
    ocr_min_confidence: float = 0.4,
    frame_dedup: bool = True,
    dedup_threshold: int = 6,
    dedup_mode: str = "bands",
) -> list[RawPost]:
    results: list[RawPost] = []
    for sc in shortcodes:
        try:
            results.append(extract_one(
                sc, settings, force=force,
                frame_interval=frame_interval,
                ocr_min_confidence=ocr_min_confidence,
                frame_dedup=frame_dedup,
                dedup_threshold=dedup_threshold,
                dedup_mode=dedup_mode,
            ))
        except Exception as e:
            console.print(f"[red]✗ {sc}: {e}")
    return results
