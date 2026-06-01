import json
import time

from instatrip.session import check_session


def _write_state(path, expires):
    path.write_text(json.dumps({
        "cookies": [
            {"name": "sessionid", "domain": ".instagram.com", "expires": expires}
        ]
    }), encoding="utf-8")


def test_check_session_missing_file(tmp_path):
    res = check_session(tmp_path / "absent.json")
    assert res["status"] == "missing"


def test_check_session_expired(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() - 86400)
    res = check_session(p)
    assert res["status"] == "expired"


def test_check_session_fresh(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() + 86400 * 30)
    res = check_session(p)
    assert res["status"] == "fresh"
    assert res["days_left"] > 20


def test_check_session_expiring(tmp_path):
    p = tmp_path / "state.json"
    _write_state(p, time.time() + 86400 * 3)
    res = check_session(p)
    assert res["status"] == "expiring"
