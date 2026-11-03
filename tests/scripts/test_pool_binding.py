"""The default pool file follows the session's binding, so a coordinator whose cwd reset to the launch folder
still reads and writes the run's pool (#84). Without a session the default stays ./.superlite/pool.json."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import SCRIPTS  # noqa: E402
from _fixtures import FIXTURES  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

SID = "pool-binding-1"
PLAN = FIXTURES / "run_plan" / "plan.md"


def tool(name, *args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / f"{name}.py"), *map(str, args)], capture_output=True,
                          text=True, cwd=cwd, encoding="utf-8", timeout=60)


def bound_run(tmp_path, monkeypatch):
    """A run folder bound to the session, and the launch folder the coordinator's cwd fell back to."""
    run, launch = tmp_path / "run", tmp_path / "launch"
    (run / ".git").mkdir(parents=True)
    (run / ".superlite").mkdir()
    launch.mkdir()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    state.bind(run / ".superlite")
    return run, launch


def test_pool_add_outside_the_run_writes_the_bound_pool(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    r = tool("pool", "add", "a1", "--tier", "sonnet", cwd=launch)
    assert r.returncode == 0, r.stderr
    agents = json.loads((run / ".superlite" / "pool.json").read_text(encoding="utf-8"))["agents"]
    assert [a["id"] for a in agents] == ["a1"]
    assert not (launch / ".superlite").exists()


def test_task_outside_the_run_reads_the_bound_pool_plan(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    (run / ".superlite" / "pool.json").write_text(json.dumps({"plan": str(PLAN), "agents": []}), encoding="utf-8")
    r = tool("task", "T1", cwd=launch)
    assert r.returncode == 0, r.stderr
    assert "parser" in r.stdout


def test_assign_outside_the_run_reads_the_bound_pool(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    (run / ".superlite" / "pool.json").write_text(json.dumps({"plan": str(PLAN), "agents": []}), encoding="utf-8")
    r = tool("assign", "--task", "T1", cwd=launch)
    assert r.returncode == 0, r.stderr


def test_without_a_session_the_pool_stays_in_the_cwd(tmp_path):
    r = tool("pool", "add", "a1", "--tier", "sonnet", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".superlite" / "pool.json").is_file()
