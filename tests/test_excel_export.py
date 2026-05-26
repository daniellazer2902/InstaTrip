from openpyxl import load_workbook

from instatrip.exporters.excel import export_excel
from instatrip.models import PostInsight


def test_export_excel_voyage_profile(tmp_path):
    insights = [
        PostInsight(
            shortcode="A",
            url="https://www.instagram.com/p/A/",
            category="lieu",
            title="Sushi Dai",
            description="Sushi du matin.",
            tags=["sushi", "petit-dej"],
            attributes={"city": "Tokyo", "neighborhood": "Toyosu"},
        ),
        PostInsight(
            shortcode="B",
            url="https://www.instagram.com/p/B/",
            category="tips",
            title="JR Pass",
            description="Acheter avant l'arrivée.",
        ),
    ]
    out = tmp_path / "japon.xlsx"
    export_excel(insights, out, profile_name="voyage")
    wb = load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers == [
        "Shortcode", "URL", "Catégorie", "Titre",
        "Ville", "Quartier", "Activité",
        "Description", "Tags",
    ]
    assert ws.cell(row=2, column=3).value == "lieu"
    assert ws.cell(row=2, column=5).value == "Tokyo"
    assert ws.cell(row=3, column=3).value == "tips"


def test_export_excel_recettes_profile(tmp_path):
    insights = [
        PostInsight(
            shortcode="R",
            url="https://www.instagram.com/p/R/",
            category="plat",
            title="Ramen Tonkotsu",
            description="Ramen riche au porc.",
            tags=["ramen", "porc"],
            attributes={"cuisine": "japonaise", "difficulte": "moyen", "temps": "2h"},
        ),
    ]
    out = tmp_path / "recettes.xlsx"
    export_excel(insights, out, profile_name="recettes")
    wb = load_workbook(out)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert "Cuisine" in headers
    assert "Difficulté" in headers
    assert "Temps" in headers
    assert ws.cell(row=2, column=3).value == "plat"
