"""#909: a failed usage reading takes the stored reading of any age (expired limits dropped); a whole-call failure
rebuilds from the store; skip_line names the skipped accounts."""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from test_accounts import acc, lim
import accounts as ac


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path))
    return tmp_path


def iso(delta_s):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_s)).isoformat()


def store(name, age_s, now, *limits, n=1):
    f = ac._store()
    f.parent.mkdir(parents=True, exist_ok=True)
    last = json.loads(f.read_text()) if f.exists() else {}
    last[name] = {"at": now - age_s, "account": {"name": name, "n": n, "limits": list(limits)}}
    f.write_text(json.dumps(last))


def limit(kind, pct, resets):
    return {**lim(kind, pct), "resets_at": resets}


def test_failed_reading_uses_old_stored_reading(capsys):
    now = time.time()
    store("a", 7200, now, limit("weekly_all", 100, iso(3600)), limit("session", 95, iso(-60)))
    out = ac.with_fallback({"accounts": [{"name": "a", "error": "timeout"}]}, now=now)
    (a,) = out["accounts"]
    assert [x["kind"] for x in a["limits"]] == ["weekly_all"] and a["error"] is None and a["stale_s"] == 7200
    assert capsys.readouterr().err.splitlines() == ["a: usage unreadable (timeout); using its reading from 2 h ago"]


def test_whole_call_failure_uses_store(capsys):
    now = time.time()
    store("a", 7200, now, limit("weekly_all", 100, iso(3600)))
    out = ac.with_fallback({}, now=now)
    assert len(out["accounts"]) == 1 and out["accounts"][0]["name"] == "a" and out["accounts"][0]["stale_s"] == 7200
    assert capsys.readouterr().err.splitlines() == ["usage: claude-profile usage gave no report; using last readings: a 2 h old"]


def test_whole_call_failure_empty_store(capsys):
    assert ac.with_fallback({}, now=time.time()) == {}
    assert capsys.readouterr().err == ""


def test_old_full_account_still_skipped():
    now = time.time()
    store("a", 7200, now, limit("weekly_all", 100, iso(3600)))
    store("b", 600, now, limit("weekly_all", 10, iso(3600)), n=2)
    usage = ac.with_fallback({}, now=now)
    assert ac.pick_account(usage, ["a", "b"]) == "b"
    assert ac.reasons(usage, ["a", "b"]) == ["a: weekly_all 100%"]


def test_age_text_examples():
    assert ac.age_text(600) == "10 min"
    assert ac.age_text(7199) == "119 min"
    assert ac.age_text(7200) == "2 h"
    assert ac.age_text(90000) == "25 h"


def test_skip_line_examples():
    U = {"accounts": [{"name": "a", "limits": [{"kind": "weekly_all", "percent": 100}]}, {"name": "b", "limits": []},
                      {"name": "c", "error": "timeout"}]}
    assert ac.skip_line(U, ["a", "b", "c"]) == "accounts skipped: a (weekly_all 100%), c (usage unreadable: timeout)"
    assert ac.skip_line(U, ["a", "b", "c"], signed_out=["d"]) == "accounts skipped: a (weekly_all 100%), c (usage unreadable: timeout), d (signed out)"
    assert ac.skip_line(U, ["b"]) is None
    assert ac.skip_line({}, ["a", "b"]) is None
    assert ac.skip_line({}, ["a"], signed_out=["d"]) == "accounts skipped: d (signed out)"
