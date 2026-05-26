import json
from unittest.mock import patch

import pytest

from instatrip.interpret_runner import run_analysis, SentinelError


def test_run_analysis_reads_sentinel(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sentinel = data_dir / ".enriched.done"

    def fake_run(cmd, cwd, timeout, check):
        sentinel.write_text(json.dumps({
            "status": "ok", "processed": 3, "skipped": 1, "failed": 0,
            "failures": [], "finished_at": "2026-05-26T10:00:00Z",
        }), encoding="utf-8")
        class R: returncode = 0
        return R()

    with patch("instatrip.interpret_runner.subprocess.run", side_effect=fake_run):
        stats = run_analysis(project_root=tmp_path, trip_context="Voyage Japon 2026")

    assert stats["status"] == "ok"
    assert stats["processed"] == 3
    assert not sentinel.exists(), "sentinelle doit être consommée"


def test_run_analysis_raises_when_sentinel_missing(tmp_path):
    (tmp_path / "data").mkdir()
    def fake_run(cmd, cwd, timeout, check):
        class R: returncode = 0
        return R()
    with patch("instatrip.interpret_runner.subprocess.run", side_effect=fake_run):
        with pytest.raises(SentinelError):
            run_analysis(project_root=tmp_path, trip_context="x")


def test_run_analysis_raises_on_error_status(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sentinel = data_dir / ".enriched.done"

    def fake_run(cmd, cwd, timeout, check):
        sentinel.write_text(
            json.dumps({"status": "error", "error": "data/raw missing"}),
            encoding="utf-8",
        )
        class R: returncode = 0
        return R()

    with patch("instatrip.interpret_runner.subprocess.run", side_effect=fake_run):
        with pytest.raises(SentinelError, match="data/raw missing"):
            run_analysis(project_root=tmp_path, trip_context="x")


def test_run_analysis_parallel_aggregates_buckets(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    for sc in ["A", "B", "C", "D", "E"]:
        (raw / f"{sc}.json").write_text("{}", encoding="utf-8")

    spawned: list[int] = []

    def fake_popen(cmd, cwd):
        prompt = cmd[2]
        worker_id = int(prompt.split("Worker ID: ")[1].split(".")[0])
        spawned.append(worker_id)
        sentinel = tmp_path / "data" / f".enriched.done.{worker_id}"
        sentinel.write_text(
            json.dumps({
                "status": "ok",
                "processed": 2 if worker_id == 0 else 1,
                "skipped": 0,
                "failed": 0,
                "failures": [],
                "finished_at": "2026-05-26T10:00:00Z",
            }),
            encoding="utf-8",
        )

        class P:
            def wait(self, timeout=None):
                return 0
        return P()

    with patch("instatrip.interpret_runner.subprocess.Popen", side_effect=fake_popen):
        stats = run_analysis(
            project_root=tmp_path, trip_context="Japon", n_workers=4
        )

    assert stats["status"] == "ok"
    assert stats["processed"] == 5
    assert sorted(spawned) == [0, 1, 2, 3]
    for wid in range(4):
        assert not (tmp_path / "data" / f".enriched.done.{wid}").exists()


def test_run_analysis_parallel_no_raw_files(tmp_path):
    (tmp_path / "data" / "raw").mkdir(parents=True)
    with patch("instatrip.interpret_runner.subprocess.Popen") as popen_mock:
        stats = run_analysis(project_root=tmp_path, n_workers=4)
    assert stats == {
        "status": "ok",
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }
    popen_mock.assert_not_called()
