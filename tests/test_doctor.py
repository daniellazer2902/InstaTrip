from instatrip.doctor import Check, build_report, has_blocking_failure, check_ig_session, check_teams_videos


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


def test_build_report_teams_check_uses_project_root(tmp_path):
    """Regression: build_report must resolve collections/ from project root, not .secrets/.

    Layout mirrors production:
        <root>/.secrets/ig_state.json   ← state_path passed to build_report
        <root>/collections/demo/input/reunion.mp4

    Before the fix, build_report called check_teams_videos(state_path.parent) which
    resolved to <root>/.secrets/collections/ — that path never exists — returning "warn".
    After the fix (state_path.parent.parent) it resolves to <root>/collections/ and
    finds the video, returning "ok".
    """
    import json, time

    # Create the .secrets dir and a minimal (already-expired-but-parseable) state file
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    state_path = secrets_dir / "ig_state.json"
    state_path.write_text(
        json.dumps({"cookies": [
            {"name": "sessionid", "domain": ".instagram.com", "expires": time.time() - 1}
        ]}),
        encoding="utf-8",
    )

    # Create the video at the real project-root collections path
    input_dir = tmp_path / "collections" / "demo" / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "reunion.mp4").write_bytes(b"")

    report = build_report(state_path)

    teams_check = next(c for c in report if c.name == "Teams videos")
    # Must find the video → "ok" (would be "warn" if base is .secrets instead of root)
    assert teams_check.status == "ok", (
        f"Expected 'ok' but got '{teams_check.status}' — "
        "base path is probably still .secrets instead of project root"
    )
    assert teams_check.blocking is False
    # The teams check alone must not contribute to a blocking failure
    assert has_blocking_failure([teams_check]) is False
