"""commit_task.import_errors and the probe worker run under the project's own interpreter (issue #41).

The producer is `_pyrun.project_python(root)`. By default the `seam` fixture swaps in a small fake
(root/.venv/bin/python when that file exists, else sys.executable); with SUPERLITE_REAL=1 it leaves
the real function in place, so the seam check reruns the same tests against real code.
"""
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import ENV, SCRIPTS, git, make_repo, run, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import _pyrun  # noqa: E402
import commit_task  # noqa: E402

PROBE_RUN = HERE.parents[1] / "skills" / "subagent-driven-development" / "probes" / "probe_run.py"
REAL = os.environ.get("SUPERLITE_REAL") == "1"

posix_only = pytest.mark.skipif(os.name == "nt", reason="the stub interpreter is a POSIX shell script")


def fake_project_python(root):
    cand = Path(root) / ".venv" / "bin" / "python"
    return str(cand) if cand.is_file() else sys.executable


@pytest.fixture(autouse=True)
def seam(monkeypatch):
    """Fake producer by default, the real _pyrun.project_python when SUPERLITE_REAL=1."""
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    if not REAL:
        monkeypatch.setattr(_pyrun, "project_python", fake_project_python)
    return _pyrun.project_python


def stub_python(root, body):
    """root/.venv/bin/python as a shell script; it is the project interpreter, so it must exist and run."""
    p = Path(root) / ".venv" / "bin" / "python"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    p.chmod(0o755)
    return p


def recording_stub(root):
    """A stub that writes argv[0], -I, -c, the root argument and the first file to argv.txt, then prints []."""
    out = Path(root) / "argv.txt"
    stub_python(root, f'{{ echo "$0"; echo "$1"; echo "$2"; echo "$4"; echo "$6"; }} > "{out}"\necho "[]"\n')
    return out


@posix_only
def test_import_check_uses_project_venv(tmp_path):
    out = recording_stub(tmp_path)
    assert commit_task.import_errors(["pkg/a.py"], root=tmp_path) == []
    assert out.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / ".venv" / "bin" / "python"), "-I", "-c", str(tmp_path), "pkg/a.py"]


@posix_only
def test_import_check_default_root_is_the_working_directory(tmp_path, monkeypatch):
    out = recording_stub(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert commit_task.import_errors(["pkg/a.py"]) == []
    argv = out.read_text(encoding="utf-8").splitlines()
    assert Path(argv[0]).resolve() == (tmp_path / ".venv" / "bin" / "python").resolve()
    assert argv[1:4] == ["-I", "-c", "."]


def test_import_check_without_venv_unchanged(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, *a, **k):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "[]\n", "")
    monkeypatch.setattr(commit_task.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    assert commit_task.import_errors(["pkg/a.py"], ["src"]) == []
    cmd = seen["cmd"]
    assert cmd[:3] == [sys.executable, "-I", "-c"]
    assert cmd[3] == commit_task.IMPORT_DRIVER and cmd[4:] == [".", json.dumps(["src"]), "pkg/a.py"]


@posix_only
def test_failed_import_check_names_interpreter(tmp_path):
    stub = stub_python(tmp_path, 'echo "boom: no module named foo" >&2\nexit 3\n')
    problems = commit_task.import_errors(["pkg/a.py"], root=tmp_path)
    assert len(problems) == 1
    file, line, msg = problems[0]
    assert file == "pkg/a.py" and line == 0
    assert msg.startswith("import check crashed") and str(stub) in msg and "boom" in msg


@posix_only
def test_unstartable_venv_interpreter_is_a_block_not_a_traceback(tmp_path):
    """root/.venv/bin/python exists but cannot start (not executable): one problem naming it, no OSError."""
    stub = stub_python(tmp_path, "echo []\n")
    stub.chmod(0o644)
    problems = commit_task.import_errors(["pkg/a.py"], root=tmp_path)
    assert len(problems) == 1
    file, line, msg = problems[0]
    assert file == "pkg/a.py" and line == 0
    assert msg.startswith("import check crashed under ") and str(stub) in msg


@posix_only
def test_failed_import_check_logs_one_incident_and_commits_nothing(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "VALUE = 1\n")
    stub = stub_python(repo, 'echo "boom" >&2\nexit 3\n')
    with open(repo / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:  # the venv is not out-of-scope work
        f.write(".venv/\n")
    env = {k: v for k, v in ENV.items() if k != "SUPERLITE_SL"}  # real incident.py, in process
    before = int(git(repo, "rev-list", "--count", "HEAD"))
    r = run("commit_task", "T1", "--plan", "plan.md", cwd=repo, env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "import src/a.py:0 import check crashed" in r.stdout and str(stub) in r.stdout
    log = repo / ".superlite" / "incidents.jsonl"
    entries = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(entries) == 1
    assert entries[0]["agent"] == "commit_task" and entries[0]["kind"] == "exception"
    assert entries[0]["file"] == "src/a.py" and "import check crashed" in entries[0]["context"]
    assert int(git(repo, "rev-list", "--count", "HEAD")) == before


def load_probe_run(tmp_path, monkeypatch):
    """probe_run as a module; its worker error file lands in tmp_path, not the system temp folder."""
    spec = importlib.util.spec_from_file_location("probe_run_callers_mod", PROBE_RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real = mod.tempfile.NamedTemporaryFile
    monkeypatch.setattr(mod.tempfile, "NamedTemporaryFile", lambda **kw: real(dir=tmp_path, **kw))
    return mod


@posix_only
def test_probe_worker_uses_project_python(tmp_path, monkeypatch):
    mod = load_probe_run(tmp_path, monkeypatch)
    stub = stub_python(tmp_path, "exit 0\n")
    if not REAL:  # the probe runner loads _pyrun by path, so its seam is its own project_python
        monkeypatch.setattr(mod, "project_python", fake_project_python)
    seen = {}

    class Stop(Exception):
        pass

    def fake_popen(cmd, *a, **k):
        seen["cmd"], seen["cwd"] = cmd, k.get("cwd")
        raise Stop

    monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
    cfg = types.SimpleNamespace(root=tmp_path, adapter=tmp_path / "adapter.py", timeout=5.0,
                                stats_lock=None, workers_started=0)
    with pytest.raises(Stop):
        mod.Worker(cfg)
    cmd = seen["cmd"]
    assert cmd[0] == str(stub)
    assert cmd[1:3] == ["-X", "utf8"] and cmd[3].endswith("probe_run.py") and "--worker" in cmd
    assert seen["cwd"] == str(tmp_path)


@posix_only
def test_probe_worker_for_a_commit_checkout_uses_the_project_venv(tmp_path, monkeypatch):
    """--commit probes a temp checkout (cfg.root) that has no .venv; the interpreter is the project's (cfg.out_root)."""
    mod = load_probe_run(tmp_path, monkeypatch)
    project, tree = tmp_path / "project", tmp_path / "probe-commit-x" / "tree"
    tree.mkdir(parents=True)
    stub = stub_python(project, "exit 0\n")
    if not REAL:
        monkeypatch.setattr(mod, "project_python", fake_project_python)
    seen = {}

    class Stop(Exception):
        pass

    def fake_popen(cmd, *a, **k):
        seen["cmd"], seen["cwd"] = cmd, k.get("cwd")
        raise Stop

    monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
    cfg = types.SimpleNamespace(root=tree, out_root=project, adapter=tmp_path / "adapter.py", timeout=5.0,
                                stats_lock=None, workers_started=0)
    with pytest.raises(Stop):
        mod.Worker(cfg)
    cmd = seen["cmd"]
    assert cmd[0] == str(stub)
    assert cmd[cmd.index("--root") + 1] == str(tree) and seen["cwd"] == str(tree)  # the worker still probes the checkout


def test_probe_worker_without_venv_keeps_sys_executable(tmp_path, monkeypatch):
    mod = load_probe_run(tmp_path, monkeypatch)
    if not REAL:
        monkeypatch.setattr(mod, "project_python", fake_project_python)
    seen = {}

    class Stop(Exception):
        pass

    def fake_popen(cmd, *a, **k):
        seen["cmd"] = cmd
        raise Stop

    monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
    cfg = types.SimpleNamespace(root=tmp_path, adapter=tmp_path / "adapter.py", timeout=5.0,
                                stats_lock=None, workers_started=0)
    with pytest.raises(Stop):
        mod.Worker(cfg)
    assert seen["cmd"][0] == sys.executable


def test_commit_respawn_stays_on_sys_executable():
    """Ruling: only the worker spawn changes; the --commit self-respawn keeps sys.executable."""
    text = PROBE_RUN.read_text(encoding="utf-8")
    assert "Popen([sys.executable, str(Path(__file__).resolve()), *args]" in text
