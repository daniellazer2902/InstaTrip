import json
from pathlib import Path

from instatrip import teams
from instatrip.teams_models import Bundle, TranscriptSegment


def test_ingest_writes_bundle(tmp_path, monkeypatch):
    col = tmp_path / "collections" / "demo"
    input_dir = col / "input"
    data_dir = col / "data"
    input_dir.mkdir(parents=True)
    (input_dir / "reunion.mp4").write_bytes(b"\x00")

    monkeypatch.setattr(teams, "extract_audio", lambda v, out: out)
    monkeypatch.setattr(
        teams, "transcribe_segments",
        lambda audio, model_size, language: [
            TranscriptSegment(start=0.0, end=5.0, text="intro"),
            TranscriptSegment(start=905.0, end=910.0, text="suite"),
        ],
    )

    def fake_sample(video, out_dir, every_seconds):
        out_dir.mkdir(parents=True, exist_ok=True)
        f = out_dir / "frame_007.jpg"
        f.write_bytes(b"img")
        return [(f, 12.0)]
    monkeypatch.setattr(teams, "sample_frames_with_timecodes", fake_sample)
    monkeypatch.setattr(teams, "dedup_frames_tc", lambda frames, **k: frames)
    monkeypatch.setattr(teams, "ocr_images", lambda paths, min_confidence, languages: ["Domain | API"])

    bundle_path = teams.ingest(
        input_dir=input_dir, data_dir=data_dir, slug="demo",
        model_size="medium", frame_interval=2.0, window_minutes=15,
        dedup_threshold=6, dedup_mode="full", ocr_confidence=0.4,
    )

    assert bundle_path == data_dir / "bundle.json"
    bundle = Bundle.model_validate_json(bundle_path.read_text(encoding="utf-8"))
    assert bundle.slug == "demo"
    assert bundle.model == "medium"
    assert len(bundle.windows) == 2
    assert bundle.windows[0].frames[0].ocr == "Domain | API"
    assert bundle.windows[0].frames[0].timecode == 12.0
    assert (data_dir / "transcript.json").exists()
