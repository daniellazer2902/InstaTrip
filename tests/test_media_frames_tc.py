from pathlib import Path

from instatrip import media


def test_timecode_for_frame():
    assert media._timecode_for_frame(Path("frame_001.jpg"), 2.0) == 0.0
    assert media._timecode_for_frame(Path("frame_002.jpg"), 2.0) == 2.0
    assert media._timecode_for_frame(Path("frame_063.jpg"), 2.0) == 124.0


def test_dedup_frames_tc_deletes_dropped(tmp_path, monkeypatch):
    # 3 frames : la 2e identique à la 1re (doit être supprimée), la 3e différente.
    paths = []
    for i in (1, 2, 3):
        p = tmp_path / f"frame_{i:03d}.jpg"
        p.write_bytes(b"data")
        paths.append((p, float((i - 1) * 2)))

    hashes = {paths[0][0]: 100, paths[1][0]: 100, paths[2][0]: 12345}  # 100^12345=12381, dist=7>6
    monkeypatch.setattr(media, "_dhash", lambda p: hashes[p])

    kept = media.dedup_frames_tc(paths, threshold=6, mode="full", delete_dropped=True)
    kept_paths = [p for p, _tc in kept]
    assert paths[0][0] in kept_paths
    assert paths[2][0] in kept_paths
    assert paths[1][0] not in kept_paths
    assert not paths[1][0].exists()  # supprimée sur disque
    assert paths[0][0].exists() and paths[2][0].exists()
    assert kept[0][1] == 0.0 and kept[1][1] == 4.0  # timecodes conservés
