from instatrip.teams_models import (
    Bundle, BundleWindow, ChapterAnalysis, ChapterRef, FrameInfo, KeyPoint,
    Synthesis, TranscriptSegment, format_timecode,
)


def test_format_timecode():
    assert format_timecode(0) == "00:00:00"
    assert format_timecode(65) == "00:01:05"
    assert format_timecode(3725) == "01:02:05"
    assert format_timecode(124.9) == "00:02:04"


def test_bundle_roundtrip():
    b = Bundle(
        slug="demo",
        source_video="input/x.mp4",
        duration_seconds=120.0,
        model="medium",
        windows=[
            BundleWindow(
                index=0, start=0.0, end=60.0, transcript="bonjour",
                frames=[FrameInfo(timecode=12.0, path="data/frames/frame_007.jpg", ocr="Domain")],
            )
        ],
    )
    dumped = b.model_dump_json()
    again = Bundle.model_validate_json(dumped)
    assert again.windows[0].frames[0].ocr == "Domain"
    assert again.windows[0].frames[0].timecode == 12.0


def test_chapter_and_synthesis_defaults():
    ch = ChapterAnalysis(index=0, title="Intro", start=0.0)
    assert ch.themes == [] and ch.key_points == [] and ch.frames == []
    syn = Synthesis(
        title="Projet X", summary="résumé",
        chapters=[ChapterRef(index=0, title="Intro", start=0.0)],
    )
    assert syn.todos == []
    assert syn.chapters[0].title == "Intro"


def test_keypoint_optional_timecode():
    kp = KeyPoint(text="point")
    assert kp.timecode is None
    kp2 = KeyPoint(text="point", timecode=742.0)
    assert kp2.timecode == 742.0
