import json, sys
import pytest
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_state as fs  # noqa: E402


@pytest.fixture(autouse=True)
def _nosid(monkeypatch):
    monkeypatch.delenv("SUPERLITE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)


def folder(tmp_path, name):
    d = tmp_path / name; d.mkdir(); return d


def fleet(d, **kw):
    fs.save(d, {**fs.default(), "on": True, "owner_session": "s1", **kw})


def pointer(sid):
    import state
    return state.home() / "sessions" / f"{sid}.fleet"


def test_remember_writes_pointer(tmp_path):
    W = folder(tmp_path, "W")
    p = fs.remember(W, "s1")
    assert p == pointer("s1") and p.read_text() == str(W.resolve()) + "\n"


def test_remember_without_session_is_none(tmp_path):
    W = folder(tmp_path, "W")
    assert fs.remember(W) is None and not pointer("s1").exists()


def test_session_fleet_owned(tmp_path):
    S = folder(tmp_path, "S"); fleet(S); fs.remember(S, "s1")
    assert fs.session_fleet("s1") == S.resolve()


def test_session_fleet_other_owner(tmp_path):
    S = folder(tmp_path, "S"); fleet(S, owner_session="s2"); fs.remember(S, "s1")
    assert fs.session_fleet("s1") is None


def test_home_follows_moved_to(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W")
    fs.save(S, {**fs.default(), "moved_to": str(W)}); fleet(W)
    assert fs.home(S) == W


def test_home_of_on_folder(tmp_path):
    W = folder(tmp_path, "W"); fleet(W)
    assert fs.home(W) == Path(W)


def test_follow_moves_fleet(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W"); (W / "stable.json").write_text("{}")
    fleet(S, workers={"W1": {"state": "busy", "task": "R1"}}); fs.remember(S, "s1")
    r = fs.follow(W, "s1")
    assert r == {"from": str(S.resolve()), "to": str(W.resolve()), "workers": 1}
    assert fs.is_on(W) and fs.load(W)["workers"]["W1"]["state_dir"] == str(S.resolve())
    assert fs.load(S)["moved_to"] == str(W.resolve()) and not fs.is_on(S)
    assert fs.home(S) == W.resolve() and fs.session_fleet("s1") == W.resolve()


def test_follow_noop_when_target_on(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W")
    fleet(S); fleet(W); fs.remember(S, "s1")
    assert fs.follow(W, "s1") is None


def test_follow_fallback(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W"); (W / "stable.json").write_text("{}")
    fleet(S, workers={"W1": {"state": "busy", "task": "R1"}})
    r = fs.follow(W, "s1", fallback=S)
    assert r == {"from": str(S.resolve()), "to": str(W.resolve()), "workers": 1}


def test_follow_never_overwrites_a_target_report(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W"); (W / "stable.json").write_text("{}")
    fleet(S); fs.remember(S, "s1")
    (S / "fleet" / "reports").mkdir(parents=True); (S / "fleet" / "reports" / "R1.md").write_text("old")
    (S / "fleet" / "reports" / "R2.md").write_text("two")
    (W / "fleet" / "reports").mkdir(parents=True); (W / "fleet" / "reports" / "R1.md").write_text("new")
    assert fs.follow(W, "s1") is not None
    assert (W / "fleet" / "reports" / "R1.md").read_text() == "new"
    assert (W / "fleet" / "reports" / "R2.md").read_text() == "two"


def test_follow_skips_a_running_lead(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W")
    fleet(S, workers={"L": {"role": "lead", "state": "busy"}}); fs.remember(S, "s1")
    before = fs.path(S).read_text()
    assert fs.follow(W, "s1") is None
    assert fs.path(S).read_text() == before and not fs.path(W).exists()


def test_follow_twice_is_a_no_op(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W"); (W / "stable.json").write_text("{}")
    fleet(S); fs.remember(S, "s1")
    assert fs.follow(W, "s1") is not None
    assert fs.follow(W, "s1") is None


def test_follow_needs_a_session_id(tmp_path):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W"); fleet(S)
    assert fs.follow(W) is None


def test_add_worker_records_state_dir(tmp_path):
    W = folder(tmp_path, "W"); fs.set_on(W, "x", [])
    w = fs.add_worker(W, "W1", "p", "a", "g", "t")
    assert w["state_dir"] == str(W.resolve())


def test_set_on_remembers_and_drops_moved_to(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    W = folder(tmp_path, "W")
    fs.save(W, {**fs.default(), "moved_to": "/elsewhere"})
    fs.set_on(W, "x", [])
    assert "moved_to" not in fs.load(W)
    assert pointer("s1").read_text() == str(W.resolve()) + "\n"


def test_follow_copy_failure_leaves_source_the_only_fleet(tmp_path, monkeypatch):
    S = folder(tmp_path, "S"); W = folder(tmp_path, "W")
    fleet(S, workers={"W1": {"state": "busy", "task": "R1"}}); fs.remember(S, "s1")
    (S / "fleet").mkdir(); (S / "fleet" / "a.md").write_text("x")
    def boom(a, b):
        raise OSError("disk full")
    monkeypatch.setattr(fs.shutil, "copy2", boom)
    assert fs.follow(W, "s1") is None
    assert not fs.is_on(W) and fs.is_on(S) and "moved_to" not in fs.load(S)
