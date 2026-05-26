from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class MediaType(str, Enum):
    IMAGE = "image"
    CAROUSEL = "carousel"
    REEL = "reel"
    VIDEO = "video"


class Category(str, Enum):
    """Catégories legacy du profil voyage. Pour les autres profils, le
    champ `PostInsight.category` est un str libre (validation côté skill)."""
    LIEU = "lieu"
    TIPS = "tips"
    ACTIVITE = "activite"
    AUTRE = "autre"


class RawPost(BaseModel):
    shortcode: str
    url: HttpUrl
    media_type: MediaType
    caption: str = ""
    pinned_comment: Optional[str] = None
    transcript: Optional[str] = None
    ocr_text: list[str] = Field(default_factory=list)
    author: Optional[str] = None


class PostInsight(BaseModel):
    """Sortie enrichie par le LLM. Les champs top-level sont universels.
    Les champs spécifiques au profil vont dans `attributes`. Pour
    backward compat, les anciens champs voyage (city/neighborhood/activity)
    sont acceptés et migrés vers `attributes` automatiquement."""
    shortcode: str
    url: HttpUrl
    category: str
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_voyage_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        attrs = dict(data.get("attributes") or {})
        for legacy_key in ("city", "neighborhood", "activity"):
            if legacy_key in data and data[legacy_key] is not None:
                attrs.setdefault(legacy_key, data.pop(legacy_key))
        if attrs:
            data["attributes"] = attrs
        return data
