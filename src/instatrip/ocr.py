from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _reader():
    import easyocr
    return easyocr.Reader(["en", "fr", "ja"], gpu=False)


def ocr_images(paths: list[Path], min_confidence: float = 0.4) -> list[str]:
    """Extrait le texte de chaque image. Retourne une liste de chaînes
    (une par image) dédupliquée, sans entrées vides."""
    reader = _reader()
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
