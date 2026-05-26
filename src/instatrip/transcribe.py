from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import torch
from faster_whisper import WhisperModel


@lru_cache(maxsize=1)
def _model(model_size: str = "small") -> WhisperModel:
    if torch.cuda.is_available():
        return WhisperModel(model_size, device="cuda", compute_type="float16")
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: Path, model_size: str = "small") -> str:
    """Transcrit un fichier audio. Retourne le texte concaténé."""
    model = _model(model_size)
    segments, _info = model.transcribe(str(audio_path), vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()
