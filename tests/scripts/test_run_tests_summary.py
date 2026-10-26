"""run_tests: per-file summary, pointer mode, Python full-run paths."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def summary(cwd, name="test-summary.json"):
    return json.loads((Path(cwd) / ".superlite" / name).read_text(encoding="utf-8"))


def tree(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    bad = tmp_path / "bench" / "tasks" / "x" / "hidden"
    bad.mkdir(parents=True)
    (bad / "test_bad.py").write_text("import not_a_real_module_zzz\n\ndef test_b():\n    pass\n")
    return tmp_path


def test_full_run_skips_bench(tmp_path):
    tree(tmp_path)
    r = rt(tmp_path, "--full")
    assert r.returncode == 0, r.stdout + r.stderr
    s = summary(tmp_path)
    assert (s["passed"], s["failed"]) == (1, 0)


def test_configured_testpaths_win(tmp_path):
    tree(tmp_path)
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = bench\n")
    r = rt(tmp_path, "--full")
    assert r.returncode != 0, r.stdout + r.stderr  # collection error: pytest exit 2 (no results)
    assert summary(tmp_path)["failed"] == 1


def test_summary_has_files(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_a():\n    assert True\n\ndef test_b():\n    assert False\n")
    rt(tmp_path, "--fast", "test_x.py")
    assert summary(tmp_path)["files"] == {"test_x.py": [1, 1]}


def test_pointer_records_mode(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_a():\n    assert True\n")
    for args, mode in ((("--fast", "test_x.py"), "fast"), (("--full",), "full")):
        r = rt(tmp_path, *args, "--background")
        assert r.returncode == 0, r.stderr
        wait = [ln for ln in r.stdout.splitlines() if ln.startswith("summary: ")][0].split(": ", 1)[1]
        ptr = json.loads((tmp_path / ".superlite" / "test-summary.latest").read_text())
        assert ptr["mode"] == mode
        w = rt(tmp_path, "--wait", wait, "--timeout", "90")
        assert w.returncode == 0, w.stdout + w.stderr


def test_python_full_args_cases(tmp_path):
    def root(name, files=(), dirs=()):
        d = tmp_path / name
        d.mkdir()
        for x in dirs:
            (d / x).mkdir()
        for fn, text in files:
            (d / fn).write_text(text)
        return d

    assert testcmd.python_full_args(root("a", dirs=("tests", "bench"))) == ["tests"]
    assert testcmd.python_full_args(root("b", [("pytest.ini", "[pytest]\ntestpaths = src\n")], ("tests", "bench"))) == []
    assert testcmd.python_full_args(root("c", [("pyproject.toml", '[tool.pytest.ini_options]\ntestpaths = ["t"]\n')], ("tests",))) == []
    assert testcmd.python_full_args(root("d", dirs=("bench",))) == ["--ignore=bench"]
    assert testcmd.python_full_args(root("e")) == []
    assert testcmd.python_full_args(root("f", [("setup.cfg", "[tool:pytest]\ntestpaths = t\n")], ("tests",))) == []
    assert testcmd.python_full_args(root("g", [("tox.ini", "[pytest]\ntestpaths = t\n")], ("tests",))) == []


def test_python_full_args_config_edge_cases(tmp_path):
    def root(name, files, dirs=("tests",)):
        d = tmp_path / name
        d.mkdir()
        for x in dirs:
            (d / x).mkdir()
        for fn, data in files:
            (d / fn).write_bytes(data)
        return d

    multi = b'[tool.pytest.ini_options]  # cfg\r\ntestpaths = [\r\n  "a",\r\n  "b",\r\n]\r\n'
    assert testcmd.python_full_args(root("m", [("pyproject.toml", multi)])) == []
    # a testpaths key in another section does not count
    assert testcmd.python_full_args(root("o", [("pyproject.toml", b'[tool.other]\ntestpaths = ["x"]\n')])) == ["tests"]
    assert testcmd.python_full_args(root("o2", [("tox.ini", b"[other]\ntestpaths = x\n")])) == ["tests"]
    # malformed or undecodable configs do not crash
    assert testcmd.python_full_args(root("bad", [("pyproject.toml", b"[[[ nope"), ("pytest.ini", b"\xff\xfe\x00 [pytest"),
                                                  ("setup.cfg", b"no section\n")])) == ["tests"]
    # bench is only ignored when it exists
    assert testcmd.python_full_args(root("nb", [], ())) == []
