"""run_tests: a test file that fails at collection is a failed test file with pytest's error text, never a crash (#196)."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
BROKEN = "import missing_mod_zzz\n\n\ndef test_a():\n    pass\n"
ERROR = "ModuleNotFoundError: No module named 'missing_mod_zzz'"
# what pytest writes for a collection error in the xunit2 family (its default): no `file` attribute, empty classname
XUNIT2 = ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" errors="1" tests="1">'
          '<testcase classname="" name="tests.test_x" time="0.000"><error message="collection failure">'
          "ImportError while importing test module '/abs/tests/test_x.py'.\nTraceback:\n"
          "tests/test_x.py:1: in &lt;module&gt;\n    import missing_mod_zzz\n"
          f"E   {ERROR}</error></testcase></testsuite></testsuites>")


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def summary(cwd):
    return json.loads((Path(cwd) / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def incidents(cwd):
    p = Path(cwd) / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def write(tmp_path, body, name="test_x.py"):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / name).write_text(body, encoding="utf-8")


def case(**attrs):
    return ET.Element("testcase", attrs)


def test_case_file_empty_classname_maps_the_name(tmp_path, monkeypatch):
    write(tmp_path, BROKEN)
    monkeypatch.chdir(tmp_path)
    assert run_tests.case_file(case(classname="", name="tests.test_x")) == "tests/test_x.py"


def test_case_file_empty_classname_never_crashes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_tests.case_file(case(classname="", name="tests.test_gone")) == "tests.test_gone"
    assert run_tests.case_file(case(classname="", name="")) == "unknown"
    assert run_tests.case_file(case()) == "unknown"


def test_parse_junit_xunit2_collection_error(tmp_path, monkeypatch):
    write(tmp_path, BROKEN)
    (tmp_path / "j.xml").write_text(XUNIT2, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    counts, failures, files = run_tests.parse_junit(tmp_path / "j.xml")
    assert (counts["passed"], counts["failed"]) == (0, 1)
    assert failures == [("tests/test_x.py", 1, f"tests.test_x: collection failure: {ERROR}")]
    assert files == {"tests/test_x.py": [0, 1]}


def test_full_run_reports_the_collection_error(tmp_path):
    """pytest stops with exit 2 on a collection error; its report names the file, so the run is red, not 'no results'."""
    write(tmp_path, BROKEN)
    write(tmp_path, "def test_ok():\n    pass\n", "test_ok.py")
    r = rt(tmp_path, "--full")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    s = summary(tmp_path)
    assert s["failed"] == 1 and "error" not in s, s
    assert s["failures"] == [f"tests/test_x.py::tests.test_x: collection failure: {ERROR}"]
    red = [e for e in incidents(tmp_path) if e["kind"] == "test-failure"]
    assert [(e["file"], e["line"]) for e in red] == [("tests/test_x.py", 1)]
    assert not [e for e in incidents(tmp_path) if e["kind"] == "no-result"]


def test_runner_command_xunit2_report_does_not_crash(tmp_path):
    """A test-cmd.json pytest command writes xunit2 (no `file` attribute): this crashed in case_file (#196)."""
    write(tmp_path, BROKEN)
    write(tmp_path, "def test_ok():\n    pass\n", "test_ok.py")
    (tmp_path / ".superlite").mkdir()
    cmd = f'"{sys.executable}" -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors --junitxml={{junit}}'
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "custom", "test": cmd}), encoding="utf-8")
    r = rt(tmp_path, "--full")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    s = summary(tmp_path)
    assert (s["passed"], s["failed"]) == (1, 1), s
    assert f"tests/test_x.py::tests.test_x: collection failure: {ERROR}" in s["failures"]


def test_collection_error_keeps_the_task_incidents_open(tmp_path):
    """A file that no longer imports ran no test: its open failures are not 'passed on a later run'."""
    write(tmp_path, "def test_a():\n    assert 1 == 2\n")
    assert rt(tmp_path, "--fast", "tests/test_x.py", "--task", "T1").returncode == 1
    write(tmp_path, BROKEN)
    assert rt(tmp_path, "--fast", "tests/test_x.py", "--task", "T1").returncode == 1
    assert not [e for e in incidents(tmp_path) if e.get("resolution") == "fixed"], incidents(tmp_path)


def test_plain_interrupt_stays_no_result(tmp_path):
    """Exit 2 without a collection error (pytest.exit, Ctrl-C) is no full result: still a no-result stop, never green."""
    write(tmp_path, "import pytest\n\n\ndef test_a():\n    pass\n\n\ndef test_b():\n    pytest.exit('halt', returncode=2)\n")
    r = rt(tmp_path, "--fast", "tests/test_x.py")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "error" in summary(tmp_path)
    assert [e["kind"] for e in incidents(tmp_path)] == ["no-result"]
