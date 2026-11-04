"""The ledger and incident-log defaults follow the session's binding, like the pool (#84, #87): a coordinator whose cwd
reset to the launch folder still reads and writes the run's `progress.md` and `incidents.jsonl`. Without a session
the defaults stay in ./.superlite."""
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

SID = "run-state-binding-1"
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


def test_state_names_the_bound_ledger_and_incident_log(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    monkeypatch.chdir(launch)
    assert Path(state.ledger_path()) == (run / ".superlite" / "progress.md").resolve()
    assert Path(state.incident_log()) == (run / ".superlite" / "incidents.jsonl").resolve()


def test_incident_add_outside_the_run_writes_the_bound_log(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    r = tool("incident", "add", "--file", "src/a.py", "--line", "3", "--kind", "unsure", "--context", "seam guess", cwd=launch)
    assert r.returncode == 0, r.stderr
    rows = [json.loads(x) for x in (run / ".superlite" / "incidents.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["file"] for x in rows] == ["src/a.py"]
    assert not (launch / ".superlite").exists()
    summary = tool("incident", "summary", cwd=launch)
    assert summary.returncode == 0 and "src/a.py" in summary.stdout, summary.stdout + summary.stderr


def test_finish_outside_the_run_reads_the_bound_ledger_and_log(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    (run / ".superlite" / "progress.md").write_text("- Ruling: keep the slim prime - measured in #53\n", encoding="utf-8")
    assert tool("incident", "add", "--file", "src/b.py", "--line", "9", "--kind", "unsure", "--context", "open one",
                cwd=run).returncode == 0
    r = tool("finish", cwd=launch)
    assert r.returncode == 0, r.stderr
    assert "keep the slim prime" in r.stdout and "src/b.py" in r.stdout, r.stdout


def test_dispatch_outside_the_run_reads_the_bound_ledger(tmp_path, monkeypatch):
    run, launch = bound_run(tmp_path, monkeypatch)
    sl = run / ".superlite"
    (sl / "pool.json").write_text(json.dumps({"plan": str(PLAN), "agents": []}), encoding="utf-8")
    before = tool("dispatch", cwd=launch)
    assert before.returncode == 0, before.stderr
    assert "T1" in before.stdout
    (sl / "progress.md").write_text("- commit T1 abc1234567 parser\n", encoding="utf-8")
    after = tool("dispatch", cwd=launch)
    assert after.returncode == 0, after.stderr
    assert not any(ln.split()[0].split(",").count("T1") for ln in after.stdout.splitlines() if ln.startswith("T"))


def test_commit_task_outside_the_run_reads_the_bound_ledger(tmp_path, monkeypatch):
    """A `Ruling: T1 also commits F` line in the bound ledger gives an Owns-less T1 its file, so commit_task gets past
    the Owns check (it then fails later on git in the launch folder, which is not this test's concern)."""
    run, launch = bound_run(tmp_path, monkeypatch)
    plan = run / "plan.md"
    plan.write_text("# Plan\n**Goal:** x.\n\n### T1 notes · Complexity 1 · Est. context 10k\n**Est. time:** 1 min\n\nBody.\n",
                    encoding="utf-8")
    (run / ".superlite" / "progress.md").write_text("- Ruling: T1 also commits notes.md - only file\n", encoding="utf-8")
    r = tool("commit_task", "T1", "--plan", plan, cwd=launch)
    assert "has no Owns line" not in r.stderr + r.stdout, r.stderr


def test_without_a_session_the_defaults_stay_in_the_cwd(tmp_path):
    r = tool("incident", "add", "--file", "x.py", "--line", "1", "--kind", "unsure", "--context", "c", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".superlite" / "incidents.jsonl").is_file()
