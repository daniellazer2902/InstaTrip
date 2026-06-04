import pytest

from instatrip.scaffold import scaffold_teams


def test_scaffold_teams_creates_input(tmp_path):
    env = scaffold_teams(tmp_path, "demo-projet")
    assert env.exists()
    content = env.read_text(encoding="utf-8")
    assert "COLLECTION_SLUG=demo-projet" in content
    assert "COLLECTION_PROFILE=teams" in content
    assert (tmp_path / "collections" / "demo-projet" / "input").is_dir()


def test_scaffold_teams_refuses_existing(tmp_path):
    scaffold_teams(tmp_path, "demo-projet")
    with pytest.raises(FileExistsError):
        scaffold_teams(tmp_path, "demo-projet")
