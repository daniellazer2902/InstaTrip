from __future__ import annotations

import json
import time
from pathlib import Path


def check_session(state_path: Path) -> dict:
    """Évalue la fraîcheur du cookie sessionid Instagram.

    Renvoie {status, expires_at, days_left}.
    status ∈ {missing, expired, expiring (<7j), fresh}."""
    if not state_path.exists():
        return {"status": "missing", "expires_at": None, "days_left": None}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "missing", "expires_at": None, "days_left": None}

    sid = next(
        (c for c in state.get("cookies", [])
         if c.get("name") == "sessionid" and "instagram.com" in c.get("domain", "")),
        None,
    )
    if not sid:
        return {"status": "missing", "expires_at": None, "days_left": None}

    expires = sid.get("expires", -1)
    if not expires or expires < 0:
        return {"status": "fresh", "expires_at": None, "days_left": None}

    days_left = (expires - time.time()) / 86400
    if days_left <= 0:
        status = "expired"
    elif days_left < 7:
        status = "expiring"
    else:
        status = "fresh"
    return {"status": status, "expires_at": expires, "days_left": days_left}


def session_warning(state_path: Path) -> str | None:
    """Message d'avertissement non bloquant si la session est périmée/absente."""
    res = check_session(state_path)
    if res["status"] in {"missing", "expired"}:
        return (
            "⚠ Session Instagram périmée ou absente. "
            "Lance `uv run instatrip auth` si le scraping échoue."
        )
    return None
