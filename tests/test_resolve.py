import json

from instatrip.models import PostInsight
from instatrip.resolve import parse_candidate, resolve_all, resolve_candidate, resolve_post


def _search_item(full, stars, desc="d"):
    return {
        "fullName": full, "name": full.split("/")[1], "description": desc,
        "stargazersCount": stars, "language": "Python", "pushedAt": "2026-10-01T00:00:00Z",
        "license": {"key": "mit"}, "isArchived": False, "url": f"https://github.com/{full}",
    }


def fake_runner(api=None, search=None):
    calls = []

    def run(args):
        calls.append(args)
        if args[0] == "api":
            return json.dumps(api) if api else None
        return json.dumps(search or [])

    run.calls = calls
    return run


def test_parse_candidate_variants():
    assert parse_candidate("https://github.com/foo/bar.git") == ("foo", "bar")
    assert parse_candidate("github.com/foo/bar/") == ("foo", "bar")
    assert parse_candidate("foo/bar") == ("foo", "bar")
    assert parse_candidate("  `Firecrawl` ") == (None, "Firecrawl")


def test_owner_repo_exact_via_api():
    api = {"full_name": "foo/bar", "html_url": "https://github.com/foo/bar", "description": "x",
           "stargazers_count": 12, "language": "Go", "pushed_at": "2026-09-01T00:00:00Z",
           "license": {"spdx_id": "MIT"}, "archived": False}
    run = fake_runner(api=api)
    r = resolve_candidate("foo/bar", runner=run, pause=0)
    assert r["confidence"] == "exact"
    assert r["full_name"] == "foo/bar" and r["stars"] == 12 and r["license"] == "MIT"
    assert len(run.calls) == 1


def test_name_only_picks_exact_name_most_starred():
    search = [_search_item("someone/firecrawl-fork", 999), _search_item("firecrawl/firecrawl", 200000),
              _search_item("other/firecrawl", 3)]
    r = resolve_candidate("FireCrawl", runner=fake_runner(search=search), pause=0)
    assert r["confidence"] == "nom-exact"
    assert r["full_name"] == "firecrawl/firecrawl"


def test_no_exact_name_is_flagged():
    search = [_search_item("a/firecrawl-mcp", 50), _search_item("b/crawl", 500)]
    r = resolve_candidate("crawler-x", runner=fake_runner(search=search), pause=0)
    assert r["confidence"] == "a-verifier"
    assert r["full_name"] == "b/crawl"


def test_nothing_found():
    r = resolve_candidate("zzz", runner=fake_runner(search=[]), pause=0)
    assert r == {"query": "zzz", "confidence": "non-resolu"}


def test_resolve_post_dedups_same_repo():
    search = [_search_item("firecrawl/firecrawl", 10)]
    ins = PostInsight(shortcode="S", url="https://www.instagram.com/p/S/", category="repo",
                      title="t", description="d",
                      attributes={"repos": ["firecrawl", "Firecrawl"]})
    out = resolve_post(ins, runner=fake_runner(search=search), pause=0)
    assert [r["full_name"] for r in out["repos"]] == ["firecrawl/firecrawl"]


def test_resolve_all_is_idempotent(tmp_path):
    enr = tmp_path / "enriched"
    enr.mkdir()
    (enr / "S.json").write_text(json.dumps({
        "shortcode": "S", "url": "https://www.instagram.com/p/S/", "category": "repo",
        "title": "t", "description": "d", "attributes": {"repos": ["firecrawl"]},
    }), encoding="utf-8")
    run = fake_runner(search=[_search_item("firecrawl/firecrawl", 10)])
    stats = resolve_all(enr, tmp_path / "resolved", runner=run, pause=0)
    assert stats["processed"] == 1 and stats["repos"] == 1
    stats = resolve_all(enr, tmp_path / "resolved", runner=run, pause=0)
    assert stats["skipped"] == 1 and stats["processed"] == 0


def test_low_star_homonym_is_flagged():
    r = resolve_candidate("Wan2GP", runner=fake_runner(search=[_search_item("x/wan2gp", 56)]), pause=0)
    assert r["confidence"] == "a-verifier" and r["full_name"] == "x/wan2gp"


def test_override_replaces_candidates_and_is_always_rerun(tmp_path):
    enr = tmp_path / "enriched"
    enr.mkdir()
    (enr / "S.json").write_text(json.dumps({
        "shortcode": "S", "url": "https://www.instagram.com/p/S/", "category": "repo",
        "title": "t", "description": "d", "attributes": {"repos": ["wan2gp"]},
    }), encoding="utf-8")
    api = {"full_name": "deepbeepmeep/WanGP", "html_url": "https://github.com/deepbeepmeep/WanGP",
           "stargazers_count": 11957}
    run = fake_runner(api=api, search=[_search_item("x/wan2gp", 56)])
    resolve_all(enr, tmp_path / "resolved", runner=run, pause=0)
    ov = tmp_path / "overrides.json"
    ov.write_text(json.dumps({"S": ["deepbeepmeep/Wan2GP"]}), encoding="utf-8")
    stats = resolve_all(enr, tmp_path / "resolved", runner=run, pause=0, overrides_file=ov)
    assert stats["processed"] == 1
    data = json.loads((tmp_path / "resolved" / "S.json").read_text(encoding="utf-8"))
    assert data["repos"][0]["full_name"] == "deepbeepmeep/WanGP"
    assert data["repos"][0]["confidence"] == "exact"