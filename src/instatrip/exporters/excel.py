from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from ..models import PostInsight
from ..profiles import get as get_profile

HEADERS = ["Shortcode", "URL", "Catégorie", "Titre", "Ville", "Quartier", "Description", "Activité", "Tags"]


def export_excel(
    insights: list[PostInsight],
    out_path: Path,
    profile_name: str = "voyage",
) -> Path:
    profile = get_profile(profile_name)
    attr_keys = [k for k, _ in profile.attribute_fields]
    attr_labels = [label for _, label in profile.attribute_fields]
    headers = ["Shortcode", "URL", "Catégorie", "Titre", *attr_labels, "Description", "Tags"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Posts"
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i in insights:
        row = [
            i.shortcode,
            str(i.url),
            i.category,
            i.title,
        ]
        for key in attr_keys:
            row.append(i.attributes.get(key) or "")
        row.append(i.description)
        row.append(", ".join(i.tags))
        ws.append(row)

    widths = [12, 40, 14, 30] + [20] * len(attr_keys) + [60, 24]
    for col, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "A2"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
