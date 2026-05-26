from pathlib import Path

from instatrip.collection import parse_post_links


def test_parse_post_links_deduplicates_and_filters():
    html = (Path(__file__).parent / "fixtures" / "collection_page.html").read_text(encoding="utf-8")
    codes = parse_post_links(html)
    assert codes == ["AAA111", "BBB222"]
