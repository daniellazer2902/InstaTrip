from pathlib import Path

from instatrip.post_page import parse_post_html, parse_post_media


def test_parse_post_html_returns_caption_author_pinned():
    html = (Path(__file__).parent / "fixtures" / "post_page.html").read_text(encoding="utf-8")
    data = parse_post_html(html)
    assert data["author"] == "foodie_tokyo"
    assert "ramen" in data["caption"].lower()
    assert "Shibuya" in data["pinned_comment"]
    assert "So good" not in (data["pinned_comment"] or "")


def test_parse_post_media_detects_video():
    html = """
    <html><head>
      <meta property="og:type" content="video.other">
      <meta property="og:video" content="https://cdn/v.mp4">
      <meta property="og:image" content="https://cdn/thumb.jpg">
    </head><body></body></html>
    """
    data = parse_post_media(html)
    assert data["is_video"] is True


def test_parse_post_media_image_post_returns_image_url():
    html = """
    <html><head>
      <meta property="og:type" content="instapp:photo">
      <meta property="og:image" content="https://cdn/photo.jpg">
    </head><body></body></html>
    """
    data = parse_post_media(html)
    assert data["is_video"] is False
    assert data["image_urls"] == ["https://cdn/photo.jpg"]
