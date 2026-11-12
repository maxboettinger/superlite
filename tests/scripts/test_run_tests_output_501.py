"""run_tests keeps every run's full output in <summary>.output.log (#501)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
from _fixtures import DISK_FREE  # noqa: E402


def run(*args, cwd):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE, PYTHONIOENCODING="utf-8")
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args)], capture_output=True, cwd=cwd, env=env, timeout=120)
    cp.out, cp.err = cp.stdout.decode("utf-8"), cp.stderr.decode("utf-8")
    return cp


def pyproject(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    print('WIRE-1')\n", encoding="utf-8")
    return tmp_path


def cmd_project(tmp_path, cmd):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "go", "isolate": False, "test": cmd, "test_file": cmd}), encoding="utf-8")
    return tmp_path


def test_output_log_path_names():
    assert run_tests.output_log_path("/r/.superlite/test-summary.json") == Path("/r/.superlite/test-summary.output.log")
    n = "/r/.superlite/test-summary-20261111T001500-123-abcdef.json"
    assert run_tests.output_log_path(n) == Path("/r/.superlite/test-summary-20261111T001500-123-abcdef.output.log")


def test_keep_output_text(tmp_path):
    s = tmp_path / "test-summary.json"
    got = run_tests.keep_output(str(s), "npm test", 1, "x\n")
    assert Path(got) == tmp_path / "test-summary.output.log"
    assert Path(got).read_text(encoding="utf-8") == "command: npm test\nexit: 1\n\nx\n"


def test_pytest_print_in_output_log(tmp_path):
    pyproject(tmp_path)
    r = run("--fast", "tests/test_a.py", cwd=tmp_path)
    assert r.returncode == 0, r.err
    m = re.search(r"run_tests: output (\S+)", r.err)
    assert m, r.err
    assert "WIRE-1" in Path(m.group(1)).read_text(encoding="utf-8")


def test_wait_names_output(tmp_path):
    pyproject(tmp_path)
    b = run("--fast", "tests/test_a.py", "--background", cwd=tmp_path)
    path = re.search(r"summary: (\S+)", b.out).group(1)
    w = run("--wait", path, cwd=tmp_path)
    lines = w.err.strip().splitlines()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert lines[-1] == "tests (fast): 1 passed, 0 failed"
    assert lines[-2] == f"output: {data['output']}"
    assert data["output"] == str(Path(path).with_suffix(".output.log"))
    assert "WIRE-1" in Path(data["output"]).read_text(encoding="utf-8")


def test_testcmd_output_log(tmp_path):
    cmd_project(tmp_path, "sh t.sh")
    (tmp_path / "t.sh").write_text("echo HELLO\necho '1 passed'\n", encoding="utf-8")
    r = run("--full", cwd=tmp_path)
    assert r.returncode == 0, r.err
    log = (tmp_path / ".superlite" / "test-summary.output.log").read_text(encoding="utf-8")
    assert "HELLO" in log and "command: sh t.sh" in log and "exit: 0" in log


def test_retention_20(tmp_path):
    for n in range(25):
        p = tmp_path / f"test-summary-{n:02d}.output.log"
        p.write_text("old", encoding="utf-8")
        os.utime(p, (1000 + n, 1000 + n))
    got = run_tests.keep_output(str(tmp_path / "test-summary.json"), "c", 0, "t")
    logs = list(tmp_path.glob("*.output.log"))
    assert len(logs) == 20
    assert Path(got) in logs


def test_unwritable_returns_empty(tmp_path):
    f = tmp_path / "afile"
    f.write_text("x", encoding="utf-8")
    assert run_tests.keep_output(str(f / "test-summary.json"), "c", 0, "t") == ""


def test_limit_kill_keeps_output(tmp_path):
    cmd_project(tmp_path, "sh -c 'echo started; sleep 30'")
    r = run("--full", "--limit", "1", cwd=tmp_path)
    assert r.returncode == 2, r.err
    data = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert "started" in Path(data["output"]).read_text(encoding="utf-8")
