import pytest

from instatrip.scaffold import scaffold_collection


def test_scaffold_creates_env(tmp_path):
    env = scaffold_collection(tmp_path, "tokyo-2027", "https://insta/saved/x/", "voyage")
    assert env.exists()
    content = env.read_text(encoding="utf-8")
    assert "COLLECTION_SLUG=tokyo-2027" in content
    assert "COLLECTION_URL=https://insta/saved/x/" in content
    assert "COLLECTION_PROFILE=voyage" in content
    assert (tmp_path / "collections" / "tokyo-2027" / "data").is_dir()


def test_scaffold_refuses_existing(tmp_path):
    scaffold_collection(tmp_path, "tokyo-2027", "https://insta/x/", "voyage")
    with pytest.raises(FileExistsError):
        scaffold_collection(tmp_path, "tokyo-2027", "https://insta/y/", "voyage")
