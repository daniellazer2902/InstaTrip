from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from ..models import PostInsight

HEADERS = ["Shortcode", "URL", "Catégorie", "Titre", "Ville", "Quartier", "Description", "Activité", "Tags"]


def export_excel(insights: list[PostInsight], out_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Posts"
    ws.append(HEADERS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i in insights:
        ws.append([
            i.shortcode,
            str(i.url),
            i.category.value,
            i.title,
            i.city or "",
            i.neighborhood or "",
            i.description,
            i.activity or "",
            ", ".join(i.tags),
        ])
    widths = [12, 40, 12, 30, 16, 20, 60, 30, 24]
    for col, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + col)].width = w
    ws.freeze_panes = "A2"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
