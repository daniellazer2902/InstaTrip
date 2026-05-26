from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from .config import Settings
from .media import download_media, extract_audio, sample_frames
from .models import MediaType, RawPost
from .ocr import ocr_images
from .post_page import fetch_post
from .transcribe import transcribe

console = Console()


def _raw_path(settings: Settings, shortcode: str) -> Path:
    return settings.raw_dir / f"{shortcode}.json"


def extract_one(shortcode: str, settings: Settings, force: bool = False) -> RawPost:
    """Pipeline phase 1 pour un post. Idempotent : si le JSON existe
    déjà, on le relit (sauf si force=True)."""
    out = _raw_path(settings, shortcode)
    if out.exists() and not force:
        console.print(f"[dim]cache hit: {shortcode}")
        return RawPost.model_validate_json(out.read_text(encoding="utf-8"))

    console.print(f"[cyan]→ {shortcode}: fetch page")
    page = fetch_post(shortcode, settings.state_path)

    console.print(f"[cyan]→ {shortcode}: download media")
    media = download_media(shortcode, settings.state_path, settings.media_dir)

    transcript: str | None = None
    ocr_text: list[str] = []
    if media["video_path"]:
        wav = settings.media_dir / f"{shortcode}.wav"
        extract_audio(media["video_path"], wav)
        console.print(f"[cyan]→ {shortcode}: transcribe")
        transcript = transcribe(wav)

        frames_dir = settings.media_dir / f"{shortcode}_frames"
        frames = sample_frames(media["video_path"], frames_dir)
        if frames:
            console.print(f"[cyan]→ {shortcode}: OCR {len(frames)} frames")
            ocr_text = ocr_images(frames)
    elif media["image_paths"]:
        console.print(f"[cyan]→ {shortcode}: OCR image(s)")
        ocr_text = ocr_images(media["image_paths"])

    media_type = MediaType.REEL if media["video_path"] else MediaType.IMAGE
    if len(media["image_paths"]) > 1 and not media["video_path"]:
        media_type = MediaType.CAROUSEL

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
    console.print(f"[green]✓ {shortcode} saved")
    return post


def extract_all(shortcodes: list[str], settings: Settings, force: bool = False) -> list[RawPost]:
    results: list[RawPost] = []
    for sc in shortcodes:
        try:
            results.append(extract_one(sc, settings, force=force))
        except Exception as e:
            console.print(f"[red]✗ {sc}: {e}")
    return results
