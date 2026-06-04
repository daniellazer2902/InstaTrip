from __future__ import annotations

import re
import shutil
from pathlib import Path

from ..teams_models import ChapterAnalysis, Synthesis, format_timecode


def _slug(title: str) -> str:
    """Titre → slug kebab-case ascii pour nom de fichier de note."""
    s = title.lower()
    s = s.replace("&", " ").replace("/", "-")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _chapter_filename(ch_index: int, title: str) -> str:
    return f"{ch_index:02d}-{_slug(title)}"


def _index_md(synthesis: Synthesis, slug: str) -> str:
    lines = [
        "---",
        f'title: "{synthesis.title}"',
        f"tags: [{', '.join(synthesis.themes)}]",
        "type: teams-video",
        "---",
        "",
        f"# {synthesis.title}",
        "",
        "## Résumé",
        "",
        synthesis.summary,
        "",
        "## 🏷️ Thématiques",
        "",
    ]
    lines += [f"- {t}" for t in synthesis.themes] or ["- (aucune)"]
    lines += ["", "## 🗂️ Sommaire", ""]
    for ref in synthesis.chapters:
        fname = _chapter_filename(ref.index, ref.title)
        lines.append(f"- [{format_timecode(ref.start)}] [[{fname}|{ref.title}]]")
    lines += ["", "## 🎯 Points importants", ""]
    for kp in synthesis.key_points:
        tc = f" [{format_timecode(kp.timecode)}]" if kp.timecode is not None else ""
        lines.append(f"- {kp.text}{tc}")
    lines += ["", "## 🧩 Décisions techniques", ""]
    for kp in synthesis.decisions:
        tc = f" [{format_timecode(kp.timecode)}]" if kp.timecode is not None else ""
        lines.append(f"- {kp.text}{tc}")
    lines += ["", "## ✅ TODO & questions ouvertes", ""]
    lines += [f"- [ ] {t}" for t in synthesis.todos] or ["- (aucune)"]
    lines.append("")
    return "\n".join(lines)


def _chapter_md(ch: ChapterAnalysis) -> str:
    lines = [
        "---",
        f'title: "{ch.title}"',
        f"tags: [{', '.join(ch.themes)}]",
        f"start: {format_timecode(ch.start)}",
        "---",
        "",
        f"# [{format_timecode(ch.start)}] {ch.title}",
        "",
        "[[_index]]",
        "",
    ]
    if ch.themes:
        lines += ["## Thèmes", "", ", ".join(ch.themes), ""]
    if ch.key_points:
        lines += ["## Points clés", ""]
        for kp in ch.key_points:
            tc = f" [{format_timecode(kp.timecode)}]" if kp.timecode is not None else ""
            lines.append(f"- {kp.text}{tc}")
        lines.append("")
    if ch.decisions:
        lines += ["## Décisions", ""]
        for kp in ch.decisions:
            tc = f" [{format_timecode(kp.timecode)}]" if kp.timecode is not None else ""
            lines.append(f"- {kp.text}{tc}")
        lines.append("")
    if ch.frames:
        lines += ["## Captures", ""]
        for fr in ch.frames:
            name = Path(fr.path).name
            lines.append(f"**[{format_timecode(fr.timecode)}]**")
            lines.append(f"![[assets/{name}]]")
            if fr.ocr:
                lines.append(f"> {fr.ocr}")
            lines.append("")
    if ch.transcript_excerpt:
        lines += ["## Extrait transcription", "", "> " + ch.transcript_excerpt, ""]
    return "\n".join(lines)


def export_teams_obsidian(
    synthesis: Synthesis,
    chapters: list[ChapterAnalysis],
    out_dir: Path,
    slug: str,
) -> Path:
    """Écrit _index.md + une note par chapitre + copie les frames dans assets/.
    Retourne le chemin de _index.md."""
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    for ch in chapters:
        for fr in ch.frames:
            src = Path(fr.path)
            if src.exists():
                shutil.copy2(src, assets / src.name)
        note = out_dir / f"{_chapter_filename(ch.index, ch.title)}.md"
        note.write_text(_chapter_md(ch), encoding="utf-8")

    index = out_dir / "_index.md"
    index.write_text(_index_md(synthesis, slug), encoding="utf-8")
    return index
