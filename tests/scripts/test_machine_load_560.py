"""machine_load (#560): count leads, fixers and xcodebuild machine-wide, limit, gate."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load as ml  # noqa: E402


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MACHINE_LIMIT", raising=False)


def _reg():
    ml.register("sl-a-w1", "fixer-sonnet", "/r1")
    ml.register("lead-b7", "lead", "/r2")
    ml.register("sl-a-w2", "fixer-opus", "/r3")


def test_count_crosses_registry_with_live():
    _reg()
    c = ml.count(live={"sl-a-w1", "lead-b7"}, procs=["/usr/bin/xcodebuild", "zsh"])
    assert c == {"leads": 1, "fixers": 1, "xcodebuild": 1, "total": 3, "herdr": True}


def test_limit_env_file_default(monkeypatch, tmp_path):
    monkeypatch.setattr(ml, "_cores", lambda: 18)
    monkeypatch.setattr(ml, "_mem_gb", lambda: 64)
    assert ml.limit() == (6, "default")
    f = ml.home() / "machine.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"limit": 3}))
    assert ml.limit() == (3, str(f))
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "4")
    assert ml.limit() == (4, "SUPERLITE_MACHINE_LIMIT")
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "0")
    monkeypatch.setattr(ml, "count", lambda *a, **k: pytest.fail("no count when unlimited"))
    assert ml.gate("x", 0) is None


def test_default_floor(monkeypatch):
    monkeypatch.setattr(ml, "_cores", lambda: 2)
    monkeypatch.setattr(ml, "_mem_gb", lambda: 8)
    assert ml.limit()[0] == 2


def _counts(monkeypatch, totals):
    it = iter(totals)

    def fake(live=None, procs=None):
        t = next(it)
        return {"leads": t - 1, "fixers": 1, "xcodebuild": 0, "total": t, "herdr": True}
    monkeypatch.setattr(ml, "count", fake)


def test_gate_busy_line(monkeypatch):
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "6")
    monkeypatch.setattr(ml, "count", lambda *a, **k: {"leads": 2, "fixers": 1, "xcodebuild": 3, "total": 6, "herdr": True})
    assert ml.gate("backlog start B7", 0) == "machine busy after 0 s: 2 leads, 1 fixer, 3 xcodebuild = 6 of limit 6"


def test_gate_waits_then_starts(monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "6")
    _counts(monkeypatch, [6, 6, 5])
    assert ml.gate("fleet spawn", 30, poll_s=0) is None
    err = capsys.readouterr().err
    busy = [x for x in err.splitlines() if x.startswith("machine busy:")]
    assert len(busy) == 1
    assert "(counted machine-wide: leads and fixers in live Herdr panes, xcodebuild processes; limit 6 from SUPERLITE_MACHINE_LIMIT); waiting up to" in busy[0]
    assert err.count("below its limit after") == 1


def test_gate_over_limit(monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "1")
    monkeypatch.setattr(ml, "count", lambda *a, **k: {"leads": 1, "fixers": 0, "xcodebuild": 0, "total": 1, "herdr": True})
    assert ml.gate("x", 0, over=True) is None
    assert "machine limit overridden (--over-limit)" in capsys.readouterr().err


def test_herdr_down_counts_processes_only(monkeypatch):
    _reg()

    def boom():
        raise RuntimeError("herdr down")
    monkeypatch.setattr(ml, "_live_names", boom)
    c = ml.count(None, ["xcodebuild"])
    assert c["herdr"] is False and c["leads"] == 0 and c["xcodebuild"] == 1 and c["total"] == 1


def test_registry_drops_stale():
    ml.register("old", "lead", "/x")
    p = ml.home() / "load" / "old.json"
    d = json.loads(p.read_text())
    d["since"] = time.time() - 25 * 3600
    p.write_text(json.dumps(d))
    ml.register("fresh", "lead", "/y")
    ml.count(live=set(), procs=[])
    assert not p.exists()
    assert (ml.home() / "load" / "fresh.json").exists()


def test_snapshot_text(monkeypatch):
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "6")
    monkeypatch.setattr(ml, "count", lambda *a, **k: {"leads": 1, "fixers": 0, "xcodebuild": 2, "total": 3, "herdr": True})
    assert ml.snapshot_text() == "machine: 1 lead, 0 fixers, 2 xcodebuild = 3 of limit 6"


def test_count_survives_malformed_registry_entries():
    d = ml._dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "list.json").write_text("[1, 2]")
    (d / "bad-since.json").write_text(json.dumps({"role": "lead", "since": "oops"}))
    (d / "null-since.json").write_text(json.dumps({"role": "lead", "since": None}))
    (d / "live-list.json").write_text("[]")
    c = ml.count(live={"live-list"}, procs=[])
    assert c["total"] == 0
