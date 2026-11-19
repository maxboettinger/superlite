"""#786: a session's fleet lives in one folder outside every worktree; each run it serves links to it."""
import os, shutil, sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_state as fs  # noqa: E402
import state  # noqa: E402


@pytest.fixture(autouse=True)
def _sid(monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)


def run(tmp_path, name):
    d = tmp_path / name / ".superlite"; d.mkdir(parents=True); (d / "stable.json").write_text("{}"); return d


def home(name="s1"):
    return (state.home() / "fleets" / name).resolve()


def same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_set_on_puts_the_fleet_in_the_session_folder(tmp_path):
    A = run(tmp_path, "A")
    fs.set_on(A, "x", ["claude1"])
    assert (A / "fleet.json").is_symlink() and same(fs.path(A), home() / "fleet.json")
    assert fs.is_on(A) and fs.load(A)["owner_session"] == "s1"
    assert fs.pointer_path("s1").read_text() == str(home()) + "\n"


def test_writes_go_through_the_link(tmp_path):
    A = run(tmp_path, "A"); fs.set_on(A, "x", [])
    fs.add_worker(A, "W1", "p1", "claude1", "implementer", "sonnet")
    assert (A / "fleet.json").is_symlink()
    assert "W1" in fs.load(home())["workers"]
    assert fs.workers(A)["W1"]["state_dir"] == str(A.resolve())


def test_removed_worktree_keeps_the_fleet(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B")
    fs.set_on(A, "x", []); fs.add_worker(A, "W1", "p1", "a", "g", "t")
    r = fs.follow(B, "s1")
    assert r["to"] == str(B.resolve()) and r["home"] == str(home())
    assert r["line"] == f"fleet: this session's fleet in {home()} now also serves {B.resolve()} (1 workers)"
    fs.add_worker(B, "W2", "p2", "a", "g", "t")
    shutil.rmtree(tmp_path / "B")
    assert fs.is_on(A) and set(fs.workers(A)) == {"W1", "W2"}
    assert fs.workers(A)["W2"]["state_dir"] == str(B.resolve())
    assert "moved_to" not in fs.load(A)


def test_follow_adopts_a_plain_fleet(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B")
    fs.save(A, {**fs.default(), "on": True, "owner_session": "s1", "workers": {"W1": {"state": "busy"}}})
    fs.remember(A, "s1")
    r = fs.follow(B, "s1")
    assert (A / "fleet.json").is_symlink() and (B / "fleet.json").is_symlink()
    assert same(fs.path(A), home() / "fleet.json") and same(fs.path(B), home() / "fleet.json")
    assert fs.load(B)["workers"]["W1"]["state_dir"] == str(A.resolve())
    assert r["from"] == str(A.resolve()) and r["line"].splitlines() == [
        f"fleet: this session's fleet moved from {A.resolve()} to {home()} (1 workers)",
        f"fleet: this session's fleet in {home()} now also serves {B.resolve()} (1 workers)"]
    assert same(fs.session_fleet("s1"), home())


def test_follow_in_its_own_run_adopts_only(tmp_path):
    A = run(tmp_path, "A")
    fs.save(A, {**fs.default(), "on": True, "owner_session": "s1"}); fs.remember(A, "s1")
    r = fs.follow(A, "s1")
    assert r["line"] == f"fleet: this session's fleet moved from {A.resolve()} to {home()} (0 workers)"
    assert fs.follow(A, "s1") is None


def test_follow_twice_is_a_no_op(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B"); fs.set_on(A, "x", [])
    assert fs.follow(B, "s1") is not None
    assert fs.follow(B, "s1") is None


def test_follow_never_takes_a_run_with_its_own_fleet_on(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B"); fs.set_on(A, "x", [])
    fs.save(B, {**fs.default(), "on": True, "owner_session": "s2"})
    assert fs.follow(B, "s1") is None and not (B / "fleet.json").is_symlink()


def test_follow_copies_no_reports(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B"); fs.set_on(A, "x", [])
    (A / "fleet" / "reports").mkdir(parents=True); (A / "fleet" / "reports" / "R1.md").write_text("a")
    assert fs.follow(B, "s1") is not None
    assert not (B / "fleet").exists()


def test_set_off_drops_the_fleet_and_the_link(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B"); fs.set_on(A, "x", []); fs.follow(B, "s1")
    fs.set_off(A)
    assert not os.path.lexists(A / "fleet.json") and not (home() / "fleet.json").exists()
    assert not fs.is_on(B)


def test_fleet_on_again_after_off_uses_the_session_folder(tmp_path):
    A = run(tmp_path, "A"); fs.set_on(A, "x", []); fs.set_off(A)
    fs.set_on(A, "y", [])
    assert fs.is_on(A) and same(fs.path(A), home() / "fleet.json") and fs.load(A)["label"] == "y"


def test_set_on_moves_a_plain_fleet_with_its_workers(tmp_path):
    A = run(tmp_path, "A")
    fs.save(A, {**fs.default(), "workers": {"W1": {"state": "busy"}}, "next": 2})
    fs.set_on(A, "x", [])
    assert (A / "fleet.json").is_symlink() and fs.load(A)["next"] == 2
    assert fs.load(A)["workers"]["W1"]["state_dir"] == str(A.resolve())


def test_second_fleet_of_a_session_gets_its_own_folder(tmp_path):
    A = run(tmp_path, "A"); B = run(tmp_path, "B")
    fs.set_on(A, "x", [])
    data = fs.load(A); data["workers"]["L"] = {"role": "lead", "state": "busy"}; fs.save(A, data)
    assert fs.follow(B, "s1") is None
    fs.set_on(B, "y", [])
    assert same(fs.path(B), home("s1-2") / "fleet.json") and same(fs.path(A), home() / "fleet.json")
    assert fs.load(A)["label"] == "x" and fs.load(B)["label"] == "y"


def test_no_session_id_keeps_the_plain_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_SESSION_ID")
    A = run(tmp_path, "A"); fs.set_on(A, "x", [])
    assert not (A / "fleet.json").is_symlink() and fs.is_on(A)
    assert not (state.home() / "fleets").exists()


def test_new_home():
    assert same(fs.new_home("s1"), state.home() / "fleets" / "s1")
    fs.save(state.home() / "fleets" / "s1", {**fs.default(), "on": True})
    assert same(fs.new_home("s1"), state.home() / "fleets" / "s1-2")


def test_prune_drops_old_fleet_folders(tmp_path):
    old = state.home() / "fleets" / "old"; old.mkdir(parents=True); (old / "fleet.json").write_text("{}")
    t = old.stat().st_mtime - state.PRUNE_S - 60
    os.utime(old / "fleet.json", (t, t)); os.utime(old, (t, t))
    A = run(tmp_path, "A"); fs.set_on(A, "x", [])
    assert not old.exists() and (state.home() / "fleets" / "s1").is_dir()


def test_lock_retries_when_the_file_became_a_link(tmp_path, monkeypatch):
    A = run(tmp_path, "A"); fs.save(A, {**fs.default(), "on": True})
    h = state.home() / "fleets" / "h"; fs.save(h, {**fs.default(), "on": True, "label": "home"})
    orig, calls = fs.path, []
    def path(sd):
        p = orig(sd)
        if not calls:
            calls.append(1); fs.link(A, h)
        return p
    monkeypatch.setattr(fs, "path", path)
    with fs.locked(A):
        label = fs.load(A)["label"]
    assert label == "home" and (h / "fleet.json.lock").exists()


def test_failed_adoption_leaves_the_run_file(tmp_path, monkeypatch):
    A = run(tmp_path, "A"); B = run(tmp_path, "B")
    fs.save(A, {**fs.default(), "on": True, "owner_session": "s1"}); fs.remember(A, "s1")
    def boom(sd, h):
        raise OSError("read-only")
    monkeypatch.setattr(fs, "link", boom)
    assert fs.follow(B, "s1") is None
    assert not (A / "fleet.json").is_symlink() and fs.is_on(A)
    assert not (state.home() / "fleets" / "s1" / "fleet.json").exists() and not fs.is_on(B)
