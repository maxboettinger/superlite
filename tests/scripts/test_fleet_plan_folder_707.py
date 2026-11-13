"""#707: --plan names a missing state folder -> exit 2; bare `.superlite` walks to the nearest run; the fleet follows only into a run."""
import json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_state as fs  # noqa: E402
import state  # noqa: E402


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for v in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(fleet, "agent_gone", lambda *a, **k: False)


def repo(tmp_path, run=True):
    r = tmp_path / "repo"
    (r / ".git").mkdir(parents=True)
    if run:
        (r / ".superlite").mkdir()
        (r / ".superlite" / "orchestrator.json").write_text("{}")
    return r


def cd(monkeypatch, d):
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(d)
    monkeypatch.setenv("PWD", str(d))


def session_fleet(S, sid="s1"):
    S.mkdir(parents=True, exist_ok=True)
    fs.save(S, {**fs.default(), "on": True, "owner_session": sid,
                "workers": {"W1": {"name": "sl-a", "state": "busy", "task": "R1", "account": "x", "pane_id": "p"}}})
    fs.remember(S, sid)


def test_status_from_empty_subfolder_reads_the_top_run(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path)
    fs.save(r / ".superlite", {**fs.default(), "on": True, "workers": {"W1": {"state": "ready", "task": None}}})
    cwd = r / ".superlite" / "fleet" / "reports"
    cd(monkeypatch, cwd)
    assert fleet.main(["status", "--plan", ".superlite"]) == 0
    assert any(l.startswith("W1") for l in capsys.readouterr().out.splitlines())
    assert not (cwd / ".superlite").exists()


def test_status_from_subfolder_without_any_run_exits_2(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, run=False)
    cwd = r / "a" / "b"
    cd(monkeypatch, cwd)
    assert fleet.main(["status", "--plan", ".superlite"]) == 2
    assert capsys.readouterr().err == f"error: --plan .superlite: no run state at {(cwd / '.superlite').resolve()}\n"
    assert not (cwd / ".superlite").exists()


@pytest.mark.parametrize("argv", [["off"], ["status"], ["spawn", "--role", "research"], ["stop", "--all"], ["report", "W1"],
                                  ["send", "W1", "--text", "hi"], ["keys", "W1", "y"], ["wait"], ["run", "--layer", "tui"], ["restore"]])
def test_missing_folder_refused_by_every_subcommand_but_on_and_name(tmp_path, capsys, argv):
    M = tmp_path / "x" / ".superlite"
    assert fleet.main(argv + ["--plan", str(M)]) == 2
    assert capsys.readouterr().err == f"error: --plan {M}: no run state at {M.resolve()}\n"
    assert not (tmp_path / "x").exists()


def test_name_with_missing_folder_still_prints(tmp_path, capsys):
    M = tmp_path / "x" / ".superlite"
    assert fleet.main(["name", "T1", "--plan", str(M)]) == 0
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1 and out.startswith("sl:")
    assert not M.exists()


def test_on_creates_the_missing_folder_and_takes_the_fleet(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, N = tmp_path / "S" / ".superlite", tmp_path / "N" / ".superlite"
    session_fleet(S)
    assert fleet.main(["on", "--plan", str(N)]) == 0
    assert fs.is_on(N) and "W1" in fs.load(N)["workers"]
    assert "fleet: this session's fleet moved from" in capsys.readouterr().err


def test_fleet_never_moves_into_a_missing_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    S, N = tmp_path / "S" / ".superlite", tmp_path / "N" / ".superlite"
    session_fleet(S)
    assert fleet.main(["status", "--plan", str(N)]) == 2
    assert fs.is_on(S) and "moved_to" not in fs.load(S)
    assert not N.exists()
    assert "moved" not in capsys.readouterr().err


def test_follow_into_a_folder_without_run_state_is_none(tmp_path):
    S, W = tmp_path / "S" / ".superlite", tmp_path / "W"
    session_fleet(S)
    W.mkdir()
    before = fs.load(S)
    assert fs.follow(W, "s1") is None
    assert not fs.path(W).exists()
    assert fs.load(S) == before
    r = fs.follow(W, "s1", named=True)
    assert r and r["to"] == str(W.resolve())


@pytest.mark.parametrize("marker", ["stable.json", "orchestrator.json", "session", "fleet.json"])
def test_follow_into_a_run_moves(tmp_path, marker):
    S, W = tmp_path / "S" / ".superlite", tmp_path / "W"
    session_fleet(S)
    W.mkdir()
    (W / marker).write_text('{"on": false}' if marker == "fleet.json" else "{}")
    assert fs.follow(W, "s1") == {"from": str(S.resolve()), "to": str(W.resolve()), "workers": 1}


def test_plan_dir_bare_value_walks_to_nearest_run(tmp_path, monkeypatch):
    r = repo(tmp_path)
    (r / "a" / ".superlite").mkdir(parents=True)
    (r / "a" / ".superlite" / "session").write_text("s\n")
    cd(monkeypatch, r / "a" / "b" / "c")
    assert state.plan_dir(".superlite").resolve() == (r / "a" / ".superlite").resolve()
    (r / "a" / ".superlite" / "session").unlink()
    assert state.plan_dir(".superlite").resolve() == (r / ".superlite").resolve()
    assert state.plan_dir("./.superlite").resolve() == (r / ".superlite").resolve()


def test_plan_dir_own_run_wins_and_other_values_unchanged(tmp_path, monkeypatch):
    r = repo(tmp_path)
    (r / "a" / ".superlite").mkdir(parents=True)
    (r / "a" / ".superlite" / "stable.json").write_text("{}")
    cd(monkeypatch, r / "a")
    assert state.plan_dir(".superlite") == r / "a" / ".superlite"
    cd(monkeypatch, r / "b")
    assert state.plan_dir(str(r / "b" / ".superlite")) == r / "b" / ".superlite"
    assert state.plan_dir("x/.superlite") == r / "b" / "x" / ".superlite"


def test_plan_dir_walk_stops_at_the_checkout_top(tmp_path, monkeypatch):
    outer = tmp_path / "outer"
    (outer / ".superlite").mkdir(parents=True)
    (outer / ".superlite" / "stable.json").write_text("{}")
    (outer / "inner" / ".git").mkdir(parents=True)
    cwd = outer / "inner" / "sub"
    cd(monkeypatch, cwd)
    assert state.plan_dir(".superlite").resolve() == (cwd / ".superlite").resolve()


def test_holds_run_state(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir(); (b / "briefs").mkdir()
    (a / "orchestrator.json").write_text("{}")
    (b / "run-config.json").write_text("{}")
    assert state.holds_run_state(a) is True
    assert state.holds_run_state(b) is False
    assert state.holds_run_state(tmp_path / "missing") is False


@pytest.mark.parametrize("value", [".superlite/", "./.superlite/", "a/../.superlite"])
def test_plan_dir_bare_value_with_trailing_slash_walks(tmp_path, monkeypatch, value):
    r = repo(tmp_path)
    cd(monkeypatch, r / "a" / "b")
    (r / "a" / "b").mkdir(parents=True, exist_ok=True)
    assert state.plan_dir(value).resolve() == (r / ".superlite").resolve()


def test_file_named_superlite_is_not_a_state_folder(tmp_path, capsys):
    f = tmp_path / "x" / ".superlite"
    f.parent.mkdir()
    f.write_text("")
    assert fleet.main(["status", "--plan", str(f)]) == 2
    assert capsys.readouterr().err == f"error: --plan {f}: no run state at {f.resolve()}\n"
