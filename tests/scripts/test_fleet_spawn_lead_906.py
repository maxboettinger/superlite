# tests/scripts/test_fleet_spawn_lead_906.py: `fleet spawn --role lead --plan P` routes to fleet_lead.start_plan_lead (#906)
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402
import fleet_lead  # noqa: E402
import fleet_state as fs  # noqa: E402
import fleet_waits  # noqa: E402
import status  # noqa: E402

REFUSE = "error: --role lead takes no --tier, --machine, --for-dispatch, --for-review, --package or --note"


@pytest.fixture
def env(tmp_path, monkeypatch):
    for v in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    a, b = tmp_path / "a", tmp_path / "b"
    (a / ".git").mkdir(parents=True)
    (a / ".superlite").mkdir()
    (b / ".git").mkdir(parents=True)
    (b / "docs" / "plans").mkdir(parents=True)
    p = b / "docs" / "plans" / "p.md"
    p.write_text("# plan\n")
    fs.save(a / ".superlite", {**fs.default(), "on": True})
    monkeypatch.chdir(a)
    calls = []
    def fake(sd, plan, brief=None, label="", over=False, machine_wait=100.0):
        calls.append((sd, plan, brief, label, over, machine_wait))
        return fake.ret
    fake.ret = (0, "W3")
    monkeypatch.setattr(fleet_lead, "start_plan_lead", fake, raising=False)
    monkeypatch.setattr(fleet, "agent_gone", lambda *x, **k: False)
    return a, b, p, calls, fake


def test_lead_spawn_routes_to_start_plan_lead(env):
    a, b, p, calls, _ = env
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p)]) == 0
    assert calls == [((a / ".superlite").resolve(), str(p), None, "", False, 100.0)]


def test_lead_spawn_does_not_follow_into_plan(env, monkeypatch):
    a, b, p, calls, _ = env
    seen = []
    monkeypatch.setattr(fleet, "_follow", lambda plan, named=False: seen.append(plan))
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p)]) == 0
    assert seen == [None]
    assert not (b / ".superlite" / "fleet.json").exists()


def test_lead_spawn_plan_without_run_state_is_not_refused(env, capsys):
    a, b, p, calls, _ = env
    assert not (b / ".superlite").exists()
    fleet.main(["spawn", "--role", "lead", "--plan", str(p)])
    assert "no run state" not in capsys.readouterr().err
    assert len(calls) == 1


@pytest.mark.parametrize("flags", [["--tier", "opus"], ["--machine", "m"], ["--for-dispatch"], ["--for-review", "T1"],
                                   ["--package", "X"], ["--note", "f"]])
def test_lead_spawn_refuses_flags(env, capsys, flags):
    a, b, p, calls, _ = env
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p), *flags]) == 2
    assert REFUSE in capsys.readouterr().err
    assert calls == []


def test_lead_spawn_refuses_missing_plan(env, capsys):
    a, b, p, calls, _ = env
    assert fleet.main(["spawn", "--role", "lead"]) == 2
    assert "error: --role lead needs --plan P (the lead's plan; with --brief F any path inside its worktree)" in capsys.readouterr().err
    assert calls == []


def test_lead_spawn_fleet_off_hint(env, capsys):
    a, b, p, calls, _ = env
    fs.save(a / ".superlite", {**fs.default(), "on": False})
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p)]) == 3
    out = capsys.readouterr().out
    assert f"BLOCKED: fleet is off in {(a / '.superlite').resolve()}; run sl fleet on first" in out
    assert "--plan" not in out.split("run sl fleet on")[1].split("first")[0]
    assert calls == []


def test_lead_spawn_wait(env, monkeypatch):
    a, b, p, calls, _ = env
    got = []
    monkeypatch.setattr(fleet_io, "wait", lambda sd, ids, tmo: got.append((sd, ids, tmo)) or 0)
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p), "--wait"]) == 0
    assert got == [((a / ".superlite").resolve(), ["W3"], 540000)]
    got.clear()
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p), "--wait", "--timeout", "9m"]) == 0
    assert got[0][2] == 540000


def test_lead_spawn_timeout_needs_wait(env, capsys):
    a, b, p, calls, _ = env
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p), "--timeout", "9m"]) == 2
    assert "--timeout needs --wait" in capsys.readouterr().err


def test_lead_spawn_exit_passes(env, monkeypatch):
    a, b, p, calls, fake = env
    fake.ret = (3, None)
    called = []
    monkeypatch.setattr(fleet_io, "wait", lambda *x: called.append(x) or 0)
    assert fleet.main(["spawn", "--role", "lead", "--plan", str(p), "--wait"]) == 3
    assert called == []


def test_status_prints_lead_progress(env, monkeypatch, capsys):
    a, b, p, calls, _ = env
    fs.save(a / ".superlite", {**fs.default(), "on": True, "workers": {
        "W1": {"name": "sl-l", "role": "lead", "state": "busy", "lead_sd": str(b / ".superlite"), "pane_id": "p"},
        "W2": {"name": "sl-i", "state": "busy", "pane_id": "q"}}})
    line = "lead W1 x: plan: none yet; workers busy 0; question: none"
    monkeypatch.setattr(status, "lead_progress", lambda wid, w: line if wid == "W1" else None, raising=False)
    monkeypatch.setattr(fleet_waits, "suffixes", lambda sd, ws: {})
    assert fleet.main(["status"]) == 0
    lines = capsys.readouterr().out.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("W1 "))
    assert lines[i + 1] == line or (lines[i + 1].startswith("W2 ") and line in lines[i + 2:])
