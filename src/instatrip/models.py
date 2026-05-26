from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class MediaType(str, Enum):
    IMAGE = "image"
    CAROUSEL = "carousel"
    REEL = "reel"
    VIDEO = "video"


class Category(str, Enum):
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
    shortcode: str
    url: HttpUrl
    category: Category
    title: str
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    description: str
    activity: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
