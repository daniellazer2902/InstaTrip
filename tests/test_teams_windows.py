import pytest

from instatrip import teams
from instatrip.teams_models import FrameInfo, TranscriptSegment


def test_build_windows_groups_by_time():
    segs = [
        TranscriptSegment(start=0.0, end=5.0, text="a"),
        TranscriptSegment(start=10.0, end=15.0, text="b"),
        TranscriptSegment(start=905.0, end=910.0, text="c"),
    ]
    frames = [
        FrameInfo(timecode=12.0, path="f1.jpg", ocr="x"),
        FrameInfo(timecode=906.0, path="f2.jpg", ocr="y"),
    ]
    windows = teams.build_windows(segs, frames, window_seconds=900)
    assert len(windows) == 2
    assert windows[0].index == 0 and windows[0].start == 0 and windows[0].end == 900
    assert windows[0].transcript == "a b"
    assert [f.path for f in windows[0].frames] == ["f1.jpg"]
    assert windows[1].index == 1 and windows[1].start == 900
    assert windows[1].transcript == "c"
    assert [f.path for f in windows[1].frames] == ["f2.jpg"]


def test_build_windows_empty():
    assert teams.build_windows([], [], window_seconds=900) == []


def test_find_input_video_picks_video(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    vid = tmp_path / "reunion.mp4"
    vid.write_bytes(b"\x00")
    assert teams.find_input_video(tmp_path) == vid


def test_find_input_video_raises_when_none(tmp_path):
    with pytest.raises(FileNotFoundError):
        teams.find_input_video(tmp_path)
