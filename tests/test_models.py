import pytest
from pydantic import ValidationError

from instatrip.models import RawPost, PostInsight, Category, MediaType


def test_rawpost_minimal():
    p = RawPost(
        shortcode="ABC123",
        url="https://www.instagram.com/p/ABC123/",
        media_type=MediaType.REEL,
        caption="Sushi à Tsukiji",
    )
    assert p.shortcode == "ABC123"
    assert p.pinned_comment is None
    assert p.transcript is None
    assert p.ocr_text == []


def test_postinsight_lieu():
    i = PostInsight(
        shortcode="ABC123",
        url="https://www.instagram.com/p/ABC123/",
        category=Category.LIEU,
        title="Sushi Dai",
        city="Tokyo",
        neighborhood="Toyosu",
        description="Petit comptoir réputé pour son omakase matinal.",
        tags=["sushi", "petit-dej"],
    )
    assert i.category is Category.LIEU
    assert i.city == "Tokyo"


def test_postinsight_tips_no_city_required():
    i = PostInsight(
        shortcode="XYZ",
        url="https://www.instagram.com/p/XYZ/",
        category=Category.TIPS,
        title="Acheter un JR Pass",
        description="Acheter avant l'arrivée au Japon, moins cher.",
    )
    assert i.city is None
    assert i.tags == []


def test_invalid_url_rejected():
    with pytest.raises(ValidationError):
        RawPost(shortcode="A", url="not-a-url", media_type=MediaType.IMAGE, caption="")
