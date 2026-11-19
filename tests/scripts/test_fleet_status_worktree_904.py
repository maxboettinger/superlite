# tests/scripts/test_fleet_status_worktree_904.py: a plain fleet status names the cwd worktree's own fleet when it read another folder and the two disagree (#904)
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_lead  # noqa: E402
import fleet_state as fs  # noqa: E402
import state  # noqa: E402


@pytest.fixture
def two(tmp_path, monkeypatch):
    for v in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fleet, "agent_gone", lambda *a, **k: False)
    monkeypatch.setattr(fleet, "_follow", lambda *a, **k: None)
    monkeypatch.setattr(fleet_lead, "backlog_hint", lambda sd, cwd: None)
    S = tmp_path / "session" / ".superlite"; S.mkdir(parents=True)
    top = tmp_path / "wt"; W = top / ".superlite"; W.mkdir(parents=True)
    monkeypatch.setattr(state, "worktree_top", lambda path=".": top)
    monkeypatch.setattr(fleet, "_sd", lambda a: S.resolve())
    return S.resolve(), W.resolve(), top


def wt_lines(out):
    return [l for l in out.splitlines() if l.startswith("worktree: ")]


def test_status_on_names_worktree_off(two, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True})
    assert fleet.main(["status"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[:2] == ["fleet: on", f"worktree: fleet is off in {W}, the folder fleet spawn --plan {W} checks (this status read {S}); run sl fleet on --plan {W} first"]


def test_status_off_names_worktree_on(two, capsys):
    S, W, _ = two
    fs.save(W, {**fs.default(), "on": True})
    assert fleet.main(["status"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[:2] == ["fleet: off", f"worktree: fleet is on in {W}, the folder fleet spawn --plan {W} uses (this status read {S}); sl fleet status --plan {W} shows its workers"]


def test_status_both_on_prints_no_worktree_line(two, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True}); fs.save(W, {**fs.default(), "on": True})
    assert fleet.main(["status"]) == 0
    assert wt_lines(capsys.readouterr().out) == []


def test_status_both_off_is_unchanged(two, capsys):
    assert fleet.main(["status"]) == 0
    assert capsys.readouterr().out == "fleet: off\n"


def test_status_reading_the_worktree_folder_prints_no_line(two, monkeypatch, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True})
    monkeypatch.setattr(fleet, "_sd", lambda a: W)
    assert fleet.main(["status"]) == 0
    assert capsys.readouterr().out == "fleet: off\n"


def test_status_outside_a_worktree_prints_no_line(two, monkeypatch, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True})
    monkeypatch.setattr(state, "worktree_top", lambda path=".": None)
    assert fleet.main(["status"]) == 0
    assert wt_lines(capsys.readouterr().out) == []


def test_status_worktree_without_superlite_prints_no_line(two, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True})
    W.rmdir()
    assert fleet.main(["status"]) == 0
    assert wt_lines(capsys.readouterr().out) == []


def test_status_with_plan_prints_no_worktree_line(two, capsys):
    S, W, _ = two
    fs.save(S, {**fs.default(), "on": True})
    assert fleet.main(["status", "--plan", str(S)]) == 0
    assert wt_lines(capsys.readouterr().out) == []


def test_worktree_line_never_says_fleet_colon(two):
    S, W, _ = two
    for on in (True, False):
        fs.save(W, {**fs.default(), "on": not on})
        line = fleet.worktree_line(S, on)
        assert line is not None and "fleet: " not in line
