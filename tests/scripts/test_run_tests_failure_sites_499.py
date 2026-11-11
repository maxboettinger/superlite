"""run_tests: Swift failures carry file and line, located failures close when a run covers their file, the runner's own no-tests line is named (#499, #510)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _fixtures import FIXTURES

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
FIX = FIXTURES / "xcode"
SPOKEN = "Tests/KitTests/SpokenTextTests.swift"
NESTED = "Tests/KitTests/Nested.swift"


def rt(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120, env=env)


def swift_project(tmp_path, out="swift_serial_failures.txt", rc="65"):
    shutil.copytree(FIX / "kit" / "Tests", tmp_path / "Tests")
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "swift", "test": "sh run.sh", "isolate": False}), encoding="utf-8")
    (tmp_path / "run.sh").write_text('cat out.txt; exit "$(cat rc)"\n', encoding="utf-8")
    feed(tmp_path, out, rc)
    return tmp_path


def feed(tmp_path, out, rc):
    shutil.copy(FIX / out, tmp_path / "out.txt")
    (tmp_path / "rc").write_text(rc, encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def incidents(tmp_path):
    p = tmp_path / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def newest(tmp_path):
    out = {}
    for e in incidents(tmp_path):
        if e.get("kind") != "verified":
            out[(e["file"], e["line"])] = e
    return out


def cmd_project(tmp_path, cmd):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"test": cmd}), encoding="utf-8")


def test_swift_failures_located(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full").returncode == 1
    s = summary(tmp_path)
    assert f"{SPOKEN}::SpokenTextTests/hugeLineIsLinear(): Expectation failed: one() == 2" in s["failures"]
    assert s["files"][SPOKEN] == [0, 4]
    assert any(e["file"] == NESTED and e["line"] == 6 and e["kind"] == "test-failure" for e in incidents(tmp_path))


def test_located_failure_closes_when_covered(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 1
    open_ = [e for e in incidents(tmp_path) if e["file"] == SPOKEN and "hugeLineIsLinear" in e["context"]]
    assert open_ and open_[0]["resolution"] == "open"
    feed(tmp_path, "swift_known_issues.txt", "0")
    assert rt(tmp_path, "--fast", SPOKEN, "--task", "T1").returncode == 0
    now = newest(tmp_path)
    huge = [e for (f, _l), e in now.items() if f == SPOKEN and e["line"] == 7]
    assert huge and all(e["resolution"] == "fixed" for e in huge)
    nested = [e for (f, _l), e in now.items() if f == NESTED]
    assert nested and all(e["resolution"] == "open" for e in nested)


def test_uncounted_run_covers_nothing(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 1
    (tmp_path / "out.txt").write_text("Foo.swift:3:5: error: x\n** TEST FAILED **\n", encoding="utf-8")
    assert rt(tmp_path, "--fast", SPOKEN, "--task", "T1").returncode == 1
    located = [e for (f, _l), e in newest(tmp_path).items() if f in (SPOKEN, NESTED)]
    assert located and all(e["resolution"] == "open" for e in located)


def test_no_tests_reason_names_runner(tmp_path):
    cmd_project(tmp_path, "echo 'No test files found, exiting with code 0'")
    assert rt(tmp_path, "--full").returncode == 1
    assert summary(tmp_path)["error"].endswith("; runner: No test files found, exiting with code 0")


def test_vitest_names_unchanged(tmp_path):
    cmd_project(tmp_path, "sh t.sh")
    (tmp_path / "t.sh").write_text("echo ' FAIL  a.test.ts > one'\necho ' Tests  1 failed | 2 passed (3)'\nexit 1\n", encoding="utf-8")
    assert rt(tmp_path, "--full").returncode == 1
    s = summary(tmp_path)
    assert s["failures"] == ["-::a.test.ts > one: failed"]
    assert (s["passed"], s["failed"]) == (2, 1)


def test_covered_files_are_not_given_the_total(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 1
    feed(tmp_path, "swift_known_issues.txt", "0")
    assert rt(tmp_path, "--fast", SPOKEN, NESTED, "--task", "T1").returncode == 0
    assert summary(tmp_path)["files"] == {}


def test_covered_file_with_remaining_failure_closes_the_passing_ones(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 1
    text = (FIX / "swift_serial_failures.txt").read_text(encoding="utf-8")
    keep = "".join(ln for ln in text.splitlines(keepends=True) if "hugeLineIsLinear" not in ln)
    (tmp_path / "out.txt").write_text(keep, encoding="utf-8")
    assert rt(tmp_path, "--fast", SPOKEN, "--task", "T1").returncode == 1
    now = newest(tmp_path)
    assert now[(SPOKEN, 7)]["resolution"] == "fixed"
    assert now[(SPOKEN, 14)]["resolution"] == "open"


def test_counted_full_run_covers_every_file(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 1
    feed(tmp_path, "swift_known_issues.txt", "0")
    assert rt(tmp_path, "--full", "--task", "T1").returncode == 0
    located = [e for (f, _l), e in newest(tmp_path).items() if f in (SPOKEN, NESTED)]
    assert located and all(e["resolution"] == "fixed" for e in located)


def test_counted_xctest_red_has_no_build_error(tmp_path):
    swift_project(tmp_path)
    assert rt(tmp_path, "--full").returncode == 1
    assert not any(f.startswith("-::build error:") for f in summary(tmp_path)["failures"])
