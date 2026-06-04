from pathlib import Path

from instatrip.exporters.obsidian_teams import export_teams_obsidian, _slug
from instatrip.teams_models import (
    ChapterAnalysis, ChapterRef, FrameInfo, KeyPoint, Synthesis,
)


def test_slug():
    assert _slug("Intro & Archi") == "intro-archi"
    assert _slug("CI/CD : pipeline") == "ci-cd-pipeline"


def test_export_teams_obsidian(tmp_path):
    frames_src = tmp_path / "frames"
    frames_src.mkdir()
    frame = frames_src / "frame_007.jpg"
    frame.write_bytes(b"img")

    synthesis = Synthesis(
        title="Projet X",
        summary="Présentation de l'archi du projet X.",
        themes=["architecture", "ci-cd"],
        key_points=[KeyPoint(text="Hexagonal", timecode=742.0)],
        decisions=[KeyPoint(text="EF Core 10", timecode=1810.0)],
        todos=["Clarifier l'auth"],
        chapters=[
            ChapterRef(index=0, title="Intro", start=0.0),
            ChapterRef(index=1, title="Archi", start=900.0),
        ],
    )
    chapters = [
        ChapterAnalysis(index=0, title="Intro", start=0.0, themes=["contexte"]),
        ChapterAnalysis(
            index=1, title="Archi", start=900.0, themes=["architecture"],
            key_points=[KeyPoint(text="Domain pur", timecode=905.0)],
            frames=[FrameInfo(timecode=906.0, path=str(frame), ocr="Domain")],
            transcript_excerpt="on a un domaine pur...",
        ),
    ]

    out_dir = tmp_path / "obsidian" / "demo"
    index = export_teams_obsidian(synthesis, chapters, out_dir, slug="demo")

    assert index == out_dir / "_index.md"
    idx_txt = index.read_text(encoding="utf-8")
    assert "# Projet X" in idx_txt
    assert "Présentation de l'archi" in idx_txt
    assert "[[01-archi|Archi]]" in idx_txt
    assert "[00:15:00]" in idx_txt
    assert "Clarifier l'auth" in idx_txt
    assert "EF Core 10" in idx_txt

    chap = (out_dir / "01-archi.md").read_text(encoding="utf-8")
    assert "[00:15:05]" in chap
    assert "![[assets/frame_007.jpg]]" in chap
    assert "[00:15:06]" in chap
    assert "[[_index]]" in chap
    assert (out_dir / "assets" / "frame_007.jpg").exists()
