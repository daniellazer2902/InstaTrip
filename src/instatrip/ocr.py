from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def _reader(languages: tuple[str, ...] = ("en", "ja")):
    import easyocr
    import torch
    return easyocr.Reader(list(languages), gpu=torch.cuda.is_available())


def ocr_images(
    paths: list[Path],
    min_confidence: float = 0.4,
    languages: tuple[str, ...] = ("en", "ja"),
) -> list[str]:
    """Extrait le texte de chaque image. Retourne une liste de chaînes
    (une par image) dédupliquée, sans entrées vides."""
    reader = _reader(tuple(languages))
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        results = reader.readtext(str(p), detail=1, paragraph=False)
        lines = [text for (_box, text, conf) in results if conf >= min_confidence]
        joined = " | ".join(lines).strip()
        if joined and joined not in seen:
            seen.add(joined)
            out.append(joined)
    return out
