from instatrip.doctor import Check, has_blocking_failure, check_ig_session, check_teams_videos


def test_has_blocking_failure_true_when_blocking_ko():
    report = [
        Check(name="ffmpeg", status="ok", blocking=True, hint=""),
        Check(name="session", status="ko", blocking=True, hint="auth"),
    ]
    assert has_blocking_failure(report) is True


def test_has_blocking_failure_false_when_only_warn():
    report = [
        Check(name="cuda", status="warn", blocking=False, hint=""),
        Check(name="ffmpeg", status="ok", blocking=True, hint=""),
    ]
    assert has_blocking_failure(report) is False


def test_check_ig_session_expired_is_blocking_ko(tmp_path):
    import json, time
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"cookies": [
        {"name": "sessionid", "domain": ".instagram.com", "expires": time.time() - 10}
    ]}), encoding="utf-8")
    c = check_ig_session(p)
    assert c.blocking is True
    assert c.status == "ko"


def test_teams_videos_no_collections_is_nonblocking(tmp_path):
    """With no collections/ dir, teams check is present and non-blocking."""
    c = check_teams_videos(tmp_path)
    assert c.name == "Teams videos"
    assert c.blocking is False
    # Must not trigger has_blocking_failure
    report = [c]
    assert has_blocking_failure(report) is False


def test_teams_videos_no_videos_is_warn_nonblocking(tmp_path):
    """collections/ exists but no videos → warn, non-blocking."""
    (tmp_path / "collections" / "demo" / "input").mkdir(parents=True)
    c = check_teams_videos(tmp_path)
    assert c.blocking is False
    assert c.status == "warn"
    assert has_blocking_failure([c]) is False


def test_teams_videos_found_is_ok_nonblocking(tmp_path):
    """A .mp4 in collections/demo/input/ → status ok, non-blocking."""
    input_dir = tmp_path / "collections" / "demo" / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "recording.mp4").write_bytes(b"")
    c = check_teams_videos(tmp_path)
    assert c.blocking is False
    assert c.status == "ok"
    assert "demo" in c.detail
    assert has_blocking_failure([c]) is False
