from instatrip import ocr


class _FakeReader:
    def __init__(self, langs):
        self.langs = langs

    def readtext(self, path, detail=1, paragraph=False):
        return [([[0, 0]], "Architecture", 0.9), ([[0, 0]], "noise", 0.1)]


def test_ocr_images_uses_requested_languages(monkeypatch, tmp_path):
    captured = {}

    def fake_reader(languages):
        captured["langs"] = languages
        return _FakeReader(languages)

    monkeypatch.setattr(ocr, "_reader", fake_reader)

    img = tmp_path / "f.jpg"
    img.write_bytes(b"x")
    out = ocr.ocr_images([img], min_confidence=0.4, languages=("fr", "en"))
    assert captured["langs"] == ("fr", "en")
    assert out == ["Architecture"]  # "noise" filtré (conf 0.1 < 0.4)
