from __future__ import annotations

from pathlib import Path

from .teams_models import BundleWindow, FrameInfo, TranscriptSegment

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
