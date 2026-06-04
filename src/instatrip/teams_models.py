from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


def format_timecode(seconds: float) -> str:
    """Secondes → 'HH:MM:SS' (tronqué)."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class FrameInfo(BaseModel):
    timecode: float
    path: str
    ocr: str = ""


class BundleWindow(BaseModel):
    index: int
    start: float
    end: float
    transcript: str
    frames: list[FrameInfo] = Field(default_factory=list)


class Bundle(BaseModel):
    slug: str
    source_video: str
    duration_seconds: float
    model: str
    windows: list[BundleWindow] = Field(default_factory=list)


class KeyPoint(BaseModel):
    text: str
    timecode: Optional[float] = None


class ChapterAnalysis(BaseModel):
    """Écrit par le skill instatrip-teams (data/analysis/chapter_NN.json)."""
    index: int
    title: str
    start: float
    themes: list[str] = Field(default_factory=list)
    key_points: list[KeyPoint] = Field(default_factory=list)
    decisions: list[KeyPoint] = Field(default_factory=list)
    frames: list[FrameInfo] = Field(default_factory=list)
    transcript_excerpt: str = ""


class ChapterRef(BaseModel):
    index: int
    title: str
    start: float


class Synthesis(BaseModel):
    """Écrit par le skill instatrip-teams (data/analysis/synthesis.json)."""
    title: str
    summary: str
    themes: list[str] = Field(default_factory=list)
    key_points: list[KeyPoint] = Field(default_factory=list)
    decisions: list[KeyPoint] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    chapters: list[ChapterRef] = Field(default_factory=list)
