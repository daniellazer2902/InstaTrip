from instatrip.exporters.obsidian import export_obsidian
from instatrip.models import PostInsight


def test_export_obsidian_voyage(tmp_path):
    insights = [
        PostInsight(
            shortcode="A", url="https://www.instagram.com/p/A/",
            category="lieu", title="Sushi Dai",
            description="Sushi du matin.", tags=["sushi"],
            attributes={"city": "Tokyo", "neighborhood": "Toyosu"},
        ),
        PostInsight(
            shortcode="B", url="https://www.instagram.com/p/B/",
            category="lieu", title="Ramen X",
            description="Tonkotsu.", tags=["ramen"],
            attributes={"city": "Tokyo", "neighborhood": "Shibuya"},
        ),
        PostInsight(
            shortcode="C", url="https://www.instagram.com/p/C/",
            category="tips", title="JR Pass",
            description="Acheter avant.",
        ),
    ]
    export_obsidian(insights, tmp_path, collection_slug="japon-2026", profile_name="voyage")

    note_a = (tmp_path / "A.md").read_text(encoding="utf-8")
    assert "category: lieu" in note_a
    assert 'title: "Sushi Dai"' in note_a
    assert "city: Tokyo" in note_a
    assert "[[Tokyo]]" in note_a
    assert "https://www.instagram.com/p/A/" in note_a

    base = (tmp_path / "japon-2026.base").read_text(encoding="utf-8")
    assert "category" in base and 'city == "Tokyo"' in base

    index = (tmp_path / "japon-2026.md").read_text(encoding="utf-8")
    assert "Profil : **voyage**" in index
    assert "[[A]]" in index and "[[B]]" in index


def test_export_obsidian_recettes(tmp_path):
    insights = [
        PostInsight(
            shortcode="R1", url="https://www.instagram.com/p/R1/",
            category="plat", title="Ramen Tonkotsu",
            description="Ramen au porc.",
            tags=["ramen", "porc"],
            attributes={"cuisine": "japonaise", "difficulte": "moyen", "temps": "2h"},
        ),
    ]
    export_obsidian(insights, tmp_path, collection_slug="recettes", profile_name="recettes")

    note = (tmp_path / "R1.md").read_text(encoding="utf-8")
    assert "category: plat" in note
    assert "cuisine: japonaise" in note
    assert "difficulte: moyen" in note
    assert "temps:" in note

    base = (tmp_path / "recettes.base").read_text(encoding="utf-8")
    assert 'category == "plat"' in base
    assert "cuisine" in base
