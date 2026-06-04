from typer.testing import CliRunner

from instatrip.cli import app
from instatrip.teams_models import ChapterAnalysis, ChapterRef, Synthesis

runner = CliRunner()


def test_teams_new_creates_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["teams", "new", "demo"])
    assert result.exit_code == 0
    assert (tmp_path / "collections" / "demo" / "input").is_dir()


def test_teams_export_builds_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    col = tmp_path / "collections" / "demo"
    analysis = col / "data" / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "synthesis.json").write_text(
        Synthesis(title="Projet X", summary="résumé",
                  chapters=[ChapterRef(index=0, title="Intro", start=0.0)]).model_dump_json(),
        encoding="utf-8",
    )
    (analysis / "chapter_00.json").write_text(
        ChapterAnalysis(index=0, title="Intro", start=0.0).model_dump_json(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["teams", "export", "--collection", "demo"])
    assert result.exit_code == 0, result.output
    index = col / "output" / "obsidian" / "demo" / "_index.md"
    assert index.exists()
    assert "# Projet X" in index.read_text(encoding="utf-8")
