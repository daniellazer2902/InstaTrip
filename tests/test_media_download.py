from instatrip.media import download_images, download_media


def test_download_images_writes_files(tmp_path, monkeypatch):
    class FakeResp:
        content = b"\xff\xd8imagedata"
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()
    monkeypatch.setattr("instatrip.media.httpx.Client", FakeClient)

    paths = download_images(["http://x/1.jpg", "http://x/2.jpg"], tmp_path, "ABC")
    assert len(paths) == 2
    assert paths[0].name == "ABC_0.jpg"
    assert paths[0].read_bytes() == b"\xff\xd8imagedata"


def test_download_media_image_post_skips_ytdlp(tmp_path, monkeypatch):
    class FakeResp:
        content = b"img"
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()
    monkeypatch.setattr("instatrip.media.httpx.Client", FakeClient)
    monkeypatch.setattr("instatrip.media.yt_dlp", None)

    result = download_media(
        "ABC", state_path=tmp_path / "state.json", media_dir=tmp_path / "m",
        is_video=False, image_urls=["http://x/1.jpg"],
    )
    assert result["video_path"] is None
    assert len(result["image_paths"]) == 1
    assert result["media_type"] == "image"
