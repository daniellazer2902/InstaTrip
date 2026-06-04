from instatrip import transcribe
from instatrip.teams_models import TranscriptSegment


class _FakeSeg:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    def transcribe(self, path, **kwargs):
        segs = [_FakeSeg(0.0, 2.0, " bonjour "), _FakeSeg(2.0, 4.0, "  le monde")]
        return segs, {"language": "fr"}


def test_transcribe_segments_keeps_timestamps(monkeypatch):
    monkeypatch.setattr(transcribe, "_model", lambda model_size="medium": _FakeModel())
    out = transcribe.transcribe_segments("audio.wav", model_size="medium", language="fr")
    assert out == [
        TranscriptSegment(start=0.0, end=2.0, text="bonjour"),
        TranscriptSegment(start=2.0, end=4.0, text="le monde"),
    ]
