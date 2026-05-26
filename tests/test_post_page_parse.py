from pathlib import Path

from instatrip.post_page import parse_post_html


def test_parse_post_html_returns_caption_author_pinned():
    html = (Path(__file__).parent / "fixtures" / "post_page.html").read_text(encoding="utf-8")
    data = parse_post_html(html)
    assert data["author"] == "foodie_tokyo"
    assert "ramen" in data["caption"].lower()
    assert "Shibuya" in data["pinned_comment"]
    assert "So good" not in (data["pinned_comment"] or "")
