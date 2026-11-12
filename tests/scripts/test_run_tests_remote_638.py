"""#638: run_tests -m with a remote test command, the behind-main hint on a red remote full run, the job-slot line."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

RUN_TESTS = SCRIPTS / "run_tests.py"
ENV_DROP = ("SUPERLITE_STATE_DIR", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
PY = sys.executable
PYTEST = f"{PY} -m pytest {{files}} -q -p no:cacheprovider"
SLOW = "import pytest\n\n\n@pytest.mark.slow\ndef test_slow():\n    assert True\n\n\ndef test_plain():\n    assert True\n"


def env():
    return {**{k: v for k, v in os.environ.items() if k not in ENV_DROP}, **GIT_ENV}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=env(), check=True, capture_output=True, text=True).stdout


def rt(proj, *args):
    return subprocess.run([PY, str(RUN_TESTS), *args], cwd=proj, env=env(), capture_output=True, text=True)


def config(proj, **kw):
    (proj / ".superlite").mkdir(exist_ok=True)
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(kw), encoding="utf-8")


def summary(proj):
    return json.loads((proj / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def marker_project(tmp_path, test_file=True, language="python"):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(SLOW, encoding="utf-8")
    cfg = {"language": language, "test": "sh -c 'echo remote; exit 1'"}
    if test_file:
        cfg["test_file"] = PYTEST
    config(tmp_path, **cfg)
    return tmp_path


def test_marker_uses_test_file_without_paths(tmp_path):
    proj = marker_project(tmp_path)
    cp = rt(proj, "-m", "slow")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert summary(proj)["passed"] == 1
    assert "-m runs" in cp.stderr


def test_marker_falls_back_to_local_runner(tmp_path):
    proj = marker_project(tmp_path, test_file=False)
    cp = rt(proj, "-m", "slow")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "the local pytest runner" in cp.stderr


def test_marker_non_python_stays_refused(tmp_path):
    proj = marker_project(tmp_path, test_file=False, language="go")
    cp = rt(proj, "-m", "slow")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "is not pytest" in cp.stderr


RED = ("import sys\nprint('FAILED tests/x.py::t - assert 0')\nprint('1 failed, 2 passed in 0.1s')\n"
       "print('job.sh: waiting for a free job slot', file=sys.stderr)\nsys.exit(1)\n")
GREEN = "print('3 passed in 0.1s')\n"


def behind_project(tmp_path, script, lock=False, behind=1):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    (main / "a.txt").write_text("a", encoding="utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    for i in range(behind):
        (main / f"b{i}.txt").write_text("b", encoding="utf-8")
        git(main, "add", "-A")
        git(main, "commit", "-q", "-m", f"more {i}")
    (wt / "cmd.py").write_text(script, encoding="utf-8")
    cfg = {"language": "python", "test": f"{PY} cmd.py"}
    if lock is False:
        cfg["lock"] = False
    config(wt, **cfg)
    return wt


def test_red_remote_full_run_behind_main_warns(tmp_path):
    wt = behind_project(tmp_path, RED)
    cp = rt(wt, "--full")
    assert cp.returncode == 1, cp.stdout + cp.stderr
    warning = summary(wt)["warning"]
    assert "lacks 1 commit" in warning and "git merge main" in warning
    assert "git merge main" in cp.stderr


def test_green_or_locked_run_no_hint(tmp_path):
    wt = behind_project(tmp_path, GREEN)
    assert rt(wt, "--full").returncode == 0
    assert "warning" not in summary(wt)
    (tmp_path / "x").mkdir()
    locked = behind_project(tmp_path / "x", RED, lock=True)
    rt(locked, "--full")
    assert "warning" not in summary(locked)


def test_job_slot_line_not_in_failure_text(tmp_path):
    wt = behind_project(tmp_path, RED)
    rt(wt, "--full")
    assert not any("job.sh" in f for f in summary(wt)["failures"])
    log = (wt / ".superlite" / "test-output.log").read_text(encoding="utf-8")
    assert "job.sh" not in log


def test_behind_main_none_outside_linked_worktree(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    import run_tests as mod
    main = tmp_path / "m"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    monkeypatch.chdir(main)
    assert mod.behind_main() is None
    monkeypatch.chdir(tmp_path)
    assert mod.behind_main() is None


def test_behind_main_counts(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    import run_tests as mod
    wt = behind_project(tmp_path, GREEN, behind=2)
    monkeypatch.chdir(wt)
    assert mod.behind_main() == (2, "main")
