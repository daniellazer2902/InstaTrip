from instatrip.doctor import Check, has_blocking_failure, check_ig_session


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
