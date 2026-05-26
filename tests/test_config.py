from pathlib import Path
from instatrip.config import Settings


def test_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("COLLECTION_SLUG", "japon-2026")
    monkeypatch.setenv("COLLECTION_URL", "https://instagram.com/x/saved/y/1/")
    monkeypatch.chdir(tmp_path)
    s = Settings.load()
    assert s.collection_slug == "japon-2026"
    assert s.raw_dir == tmp_path / "data" / "raw"
    assert s.enriched_dir == tmp_path / "data" / "enriched"
    assert s.media_dir == tmp_path / "data" / "media"
    assert s.state_path == tmp_path / ".secrets" / "ig_state.json"
    assert s.raw_dir.exists()
    assert s.media_dir.exists()
    assert s.state_path.parent.exists()
