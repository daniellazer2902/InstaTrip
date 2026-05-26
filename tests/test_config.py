from instatrip.config import Settings


def test_settings_collection_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("COLLECTION_SLUG", "japon-2026")
    monkeypatch.setenv("COLLECTION_URL", "https://instagram.com/x/saved/y/1/")
    monkeypatch.chdir(tmp_path)

    s = Settings.load()
    col = tmp_path / "collections" / "japon-2026"
    assert s.collection_slug == "japon-2026"
    assert s.collection_root == col
    assert s.raw_dir == col / "data" / "raw"
    assert s.enriched_dir == col / "data" / "enriched"
    assert s.media_dir == col / "data" / "media"
    assert s.output_dir == col / "output"
    assert s.obsidian_dir == col / "output" / "obsidian"
    assert s.shortcodes_file == col / "data" / "shortcodes.json"
    # state path est partagé au niveau projet (pas par collection)
    assert s.state_path == tmp_path / ".secrets" / "ig_state.json"

    assert s.raw_dir.exists()
    assert s.media_dir.exists()
    assert s.state_path.parent.exists()


def test_settings_collection_override(tmp_path, monkeypatch):
    """L'argument explicite override l'env COLLECTION_SLUG."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("COLLECTION_SLUG", "japon-2026")
    monkeypatch.chdir(tmp_path)

    s = Settings.load(collection="recettes-asia")
    assert s.collection_slug == "recettes-asia"
    assert s.collection_root == tmp_path / "collections" / "recettes-asia"
