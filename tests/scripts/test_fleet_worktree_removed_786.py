"""#786: removing a worktree the session's fleet served leaves the fleet and its workers in the session folder."""
import shutil, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_state as fs  # noqa: E402
import state  # noqa: E402


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for v in ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.setattr(fleet, "agent_gone", lambda *a, **k: False)


def run(tmp_path, name):
    d = tmp_path / name / ".superlite"; d.mkdir(parents=True); (d / "stable.json").write_text("{}"); return d


def worker(sd, wid, task):
    data = fs.load(sd)
    data["workers"][wid] = {"name": "sl-" + wid.lower(), "state": "busy", "task": task, "account": "x", "pane_id": "p", "state_dir": str(sd.resolve())}
    fs.save(sd, data)


def test_status_in_a_lists_workers_after_b_is_removed(tmp_path, capsys):
    A, B = run(tmp_path, "A"), run(tmp_path, "B")
    assert fleet.main(["on", "--plan", str(A)]) == 0
    worker(A, "W1", "T1")
    assert fleet.main(["status", "--plan", str(B)]) == 0
    worker(B, "W2", "T2")
    shutil.rmtree(tmp_path / "B")
    capsys.readouterr()
    assert fleet.main(["status", "--plan", str(A)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "fleet: on"
    assert any(l.startswith("W1 busy") for l in out) and any(l.startswith("W2 busy") for l in out)


def test_fleet_file_lives_outside_the_runs(tmp_path):
    A = run(tmp_path, "A")
    assert fleet.main(["on", "--plan", str(A)]) == 0
    assert (A / "fleet.json").is_symlink()
    assert fs.path(A).resolve() == (state.home() / "fleets" / "s1" / "fleet.json").resolve()
