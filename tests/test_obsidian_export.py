from instatrip.exporters.obsidian import export_obsidian
from instatrip.models import Category, PostInsight


def test_export_obsidian_creates_notes_and_index(tmp_path):
    insights = [
        PostInsight(
            shortcode="A", url="https://www.instagram.com/p/A/",
            category=Category.LIEU, title="Sushi Dai",
            city="Tokyo", neighborhood="Toyosu",
            description="Sushi du matin.", tags=["sushi"],
        ),
        PostInsight(
            shortcode="B", url="https://www.instagram.com/p/B/",
            category=Category.LIEU, title="Ramen X",
            city="Tokyo", neighborhood="Shibuya",
            description="Tonkotsu.", tags=["ramen"],
        ),
        PostInsight(
            shortcode="C", url="https://www.instagram.com/p/C/",
            category=Category.TIPS, title="JR Pass",
            description="Acheter avant.",
        ),
    ]
    export_obsidian(insights, tmp_path, collection_slug="japon-2026")

    note_a = (tmp_path / "A.md").read_text(encoding="utf-8")
    assert "category: lieu" in note_a
    assert "[[Tokyo]]" in note_a
    assert "https://www.instagram.com/p/A/" in note_a

    index = (tmp_path / "japon-2026.md").read_text(encoding="utf-8")
    assert "## Tokyo" in index
    assert "[[A]]" in index and "[[B]]" in index
    assert "## Tips" in index
    assert "[[C]]" in index
