from __future__ import annotations

from pathlib import Path

import json

from .media import extract_audio, sample_frames_with_timecodes, dedup_frames_tc
from .ocr import ocr_images
from .transcribe import transcribe_segments
from .teams_models import Bundle, BundleWindow, FrameInfo, TranscriptSegment

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}


def find_input_video(input_dir: Path) -> Path:
    """Retourne la 1re vidéo trouvée dans input_dir (tri alpha). Lève si aucune."""
    for f in sorted(input_dir.iterdir()) if input_dir.exists() else []:
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
            return f
    raise FileNotFoundError(
        f"Aucune vidéo dans {input_dir} (extensions: {', '.join(sorted(VIDEO_EXTS))})"
    )


def build_windows(
    segments: list[TranscriptSegment],
    frames: list[FrameInfo],
    window_seconds: float = 900,
) -> list[BundleWindow]:
    """Regroupe segments et frames en fenêtres temporelles de window_seconds.
    Un segment/frame est rattaché à la fenêtre contenant son `start`/`timecode`."""
    if not segments and not frames:
        return []

    max_t = 0.0
    if segments:
        max_t = max(max_t, max(s.start for s in segments))
    if frames:
        max_t = max(max_t, max(f.timecode for f in frames))
    n_windows = int(max_t // window_seconds) + 1

    windows: list[BundleWindow] = []
    for idx in range(n_windows):
        w_start = idx * window_seconds
        w_end = w_start + window_seconds
        texts = [s.text for s in segments if w_start <= s.start < w_end]
        w_frames = [f for f in frames if w_start <= f.timecode < w_end]
        if not texts and not w_frames:
            continue
        windows.append(
            BundleWindow(
                index=idx,
                start=w_start,
                end=w_end,
                transcript=" ".join(t for t in texts if t).strip(),
                frames=w_frames,
            )
        )
    # ré-indexe séquentiellement (au cas où des fenêtres vides ont été sautées)
    for new_idx, w in enumerate(windows):
        w.index = new_idx
    return windows


def ingest(
    *,
    input_dir: Path,
    data_dir: Path,
    slug: str,
    model_size: str = "medium",
    frame_interval: float = 0.5,
    window_minutes: float = 15,
    dedup_threshold: int = 6,
    dedup_mode: str = "bands",
    ocr_confidence: float = 0.4,
) -> Path:
    """Extraction mécanique d'une vidéo Teams → data/bundle.json.
    Écrit aussi data/transcript.json. Réutilise media/transcribe/ocr."""
    data_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = data_dir / "frames"

    video = find_input_video(input_dir)

    audio = extract_audio(video, data_dir / "audio.wav")
    segments = transcribe_segments(audio, model_size=model_size, language="fr")
    (data_dir / "transcript.json").write_text(
        json.dumps([s.model_dump() for s in segments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    sampled = sample_frames_with_timecodes(video, frames_dir, frame_interval)
    kept = dedup_frames_tc(
        sampled, threshold=dedup_threshold, mode=dedup_mode, delete_dropped=True
    )
    frames: list[FrameInfo] = []
    for path, tc in kept:
        texts = ocr_images([path], min_confidence=ocr_confidence, languages=("fr", "en"))
        frames.append(
            FrameInfo(timecode=tc, path=str(path), ocr=texts[0] if texts else "")
        )

    duration = 0.0
    if segments:
        duration = max(duration, max(s.end for s in segments))
    if frames:
        duration = max(duration, max(f.timecode for f in frames))

    windows = build_windows(segments, frames, window_seconds=window_minutes * 60)
    bundle = Bundle(
        slug=slug,
        source_video=str(video),
        duration_seconds=duration,
        model=model_size,
        windows=windows,
    )
    bundle_path = data_dir / "bundle.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    return bundle_path
