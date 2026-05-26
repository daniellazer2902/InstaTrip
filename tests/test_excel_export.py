from openpyxl import load_workbook

from instatrip.exporters.excel import export_excel
from instatrip.models import Category, PostInsight


def test_export_excel_writes_rows(tmp_path):
    insights = [
        PostInsight(
            shortcode="A",
            url="https://www.instagram.com/p/A/",
            category=Category.LIEU,
            title="Sushi Dai",
            city="Tokyo",
            neighborhood="Toyosu",
            description="Sushi du matin.",
            tags=["sushi", "petit-dej"],
        ),
        PostInsight(
            shortcode="B",
            url="https://www.instagram.com/p/B/",
            category=Category.TIPS,
            title="JR Pass",
            description="Acheter avant l'arrivée.",
        ),
    ]
    out = tmp_path / "japon.xlsx"
    export_excel(insights, out)
    wb = load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers == ["Shortcode", "URL", "Catégorie", "Titre", "Ville", "Quartier", "Description", "Activité", "Tags"]
    assert ws.cell(row=2, column=3).value == "lieu"
    assert ws.cell(row=2, column=5).value == "Tokyo"
    assert ws.cell(row=3, column=3).value == "tips"
