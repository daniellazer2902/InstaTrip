import pytest
from pydantic import ValidationError

from instatrip.models import Category, MediaType, PostInsight, RawPost


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


def test_postinsight_with_attributes():
    """Profil voyage : attributes contient city/neighborhood/activity."""
    i = PostInsight(
        shortcode="ABC123",
        url="https://www.instagram.com/p/ABC123/",
        category="lieu",
        title="Sushi Dai",
        description="Petit comptoir réputé pour son omakase matinal.",
        tags=["sushi", "petit-dej"],
        attributes={"city": "Tokyo", "neighborhood": "Toyosu"},
    )
    assert i.category == "lieu"
    assert i.attributes["city"] == "Tokyo"
    assert i.attributes["neighborhood"] == "Toyosu"


def test_postinsight_minimal():
    i = PostInsight(
        shortcode="XYZ",
        url="https://www.instagram.com/p/XYZ/",
        category="tips",
        title="Acheter un JR Pass",
        description="Acheter avant l'arrivée au Japon, moins cher.",
    )
    assert i.attributes == {}
    assert i.tags == []
    assert i.category == "tips"


def test_postinsight_legacy_voyage_fields_migrated():
    """Backward compat : les anciens JSONs voyage avec city/neighborhood/
    activity top-level sont migrés automatiquement vers attributes."""
    i = PostInsight.model_validate({
        "shortcode": "OLD",
        "url": "https://www.instagram.com/p/OLD/",
        "category": "lieu",
        "title": "Ancienne note",
        "description": "Données pré-refactor.",
        "city": "Tokyo",
        "neighborhood": "Shibuya",
        "activity": "Voir Hachiko",
    })
    assert i.attributes["city"] == "Tokyo"
    assert i.attributes["neighborhood"] == "Shibuya"
    assert i.attributes["activity"] == "Voir Hachiko"


def test_postinsight_accepts_any_category_string():
    """Pour les profils non-voyage, category est un str libre."""
    i = PostInsight(
        shortcode="R",
        url="https://www.instagram.com/p/R/",
        category="dessert",
        title="Tarte tatin",
        description="Pomme caramélisée.",
    )
    assert i.category == "dessert"


def test_invalid_url_rejected():
    with pytest.raises(ValidationError):
        RawPost(shortcode="A", url="not-a-url", media_type=MediaType.IMAGE, caption="")


def test_legacy_category_enum_still_exists():
    """Category enum exposé pour code legacy / voyage profile."""
    assert Category.LIEU.value == "lieu"
    assert Category.TIPS.value == "tips"
