"""A project command runs in its package folder; a missing scheme is a no-result stop (#817)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts"
sys.path.insert(0, str(SCRIPTS))

import run_tests as rt  # noqa: E402
from test_plan_tools import make_plan  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
FOLDER = "Packages/Kit"


def git(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True, env=env)


def project(tmp_path, cfg, maxapp=False, fake=None):
    kit = tmp_path / FOLDER
    (kit / "tests").mkdir(parents=True)
    (kit / "Package.swift").write_text("// package", encoding="utf-8")
    (kit / "tests" / "a_test.sh").write_text("echo ok", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\nbin/\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    if maxapp:
        (tmp_path / ".maxapp").write_text(f"package={FOLDER}\npackage_scheme=Kit-Package\n", encoding="utf-8")
    if fake is not None:
        (tmp_path / "bin").mkdir()
        x = tmp_path / "bin" / "xcodebuild"
        x.write_text(fake, encoding="utf-8")
        x.chmod(0o755)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")


def go(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    env.update(SUPERLITE_GUI_CHECK="0", PYTHONIOENCODING="utf-8", PATH=f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *args], capture_output=True, cwd=tmp_path, env=env, timeout=120)
    cp.out, cp.err = cp.stdout.decode("utf-8"), cp.stderr.decode("utf-8")
    cp.both = cp.out + cp.err
    return cp


def pwd_cmd(tmp_path, extra=""):
    return f"pwd > {tmp_path / 'pwd.txt'}; {extra}echo 1 passed"


def written(tmp_path):
    return (tmp_path / "pwd.txt").read_text(encoding="utf-8").strip()


def incidents(tmp_path):
    p = tmp_path / ".superlite" / "incidents.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def fake_xcodebuild(tmp_path):
    return f"#!/bin/sh\npwd > {tmp_path / 'pwd.txt'}\necho 1 passed\n"


def test_cwd_key_runs_in_that_folder(tmp_path):
    cmd = pwd_cmd(tmp_path)
    project(tmp_path, {"language": "other", "test": cmd, "cwd": FOLDER, "isolate": False})
    cp = go(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert written(tmp_path).endswith("/Packages/Kit")
    assert "run_tests: runs in Packages/Kit (test-cmd.json cwd)" in cp.err


def test_cwd_key_applies_in_a_task_tree(tmp_path):
    cmd = pwd_cmd(tmp_path, "echo {files} > /dev/null; ")
    project(tmp_path, {"language": "other", "test": cmd, "test_file": cmd, "cwd": FOLDER, "isolate": True})
    plan = make_plan(tmp_path, [{"id": "T1", "owns": f"{FOLDER}/tests/a_test.sh"}], name="p.md")
    (tmp_path / FOLDER / "tests" / "a_test.sh").write_text("echo changed", encoding="utf-8")
    cp = go(tmp_path, "--fast", f"{FOLDER}/tests/a_test.sh", "--task", "T1", "--plan", str(plan))
    assert cp.returncode == 0, cp.both
    assert written(tmp_path).endswith(".superlite/trees/T1/Packages/Kit")


def test_fast_files_relative_to_the_folder(tmp_path):
    out = tmp_path / "files.txt"
    cmd = f"echo {{files}} > {out}; echo 1 passed"
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "test_file": cmd, "cwd": FOLDER, "isolate": False})
    cp = go(tmp_path, "--fast", f"{FOLDER}/tests/a_test.sh")
    assert cp.returncode == 0, cp.both
    assert out.read_text(encoding="utf-8") == "tests/a_test.sh\n"


@pytest.mark.parametrize("value", ["../x", "/abs", "", 3])
def test_bad_cwd_is_a_usage_error(tmp_path, value):
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "cwd": value, "isolate": False})
    cp = go(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    assert f'test-cmd.json "cwd" must be a relative folder inside the project: {value}' in cp.err
    assert incidents(tmp_path) == []


def test_missing_cwd_folder_is_a_usage_error(tmp_path):
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "cwd": "Nope", "isolate": False})
    cp = go(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    assert 'test-cmd.json "cwd" folder not found: Nope' in cp.err
    assert incidents(tmp_path) == []


def test_maxapp_package_for_its_scheme(tmp_path):
    project(tmp_path, {"language": "other", "test": "xcodebuild -scheme Kit-Package test", "isolate": False}, maxapp=True, fake=fake_xcodebuild(tmp_path))
    cp = go(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert written(tmp_path).endswith("/Packages/Kit")
    for other in ("xcodebuild -scheme Other test", "cd Packages/Kit && xcodebuild -scheme Kit-Package test"):
        (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "other", "test": other, "isolate": False}), encoding="utf-8")
        (tmp_path / "pwd.txt").unlink()
        cp = go(tmp_path, "--full")
        assert cp.returncode == 0, cp.both
        assert "run_tests: runs in" not in cp.err, other


def test_run_folder_unit(tmp_path):
    (tmp_path / FOLDER).mkdir(parents=True)
    (tmp_path / ".maxapp").write_text(f"package={FOLDER}\npackage_scheme=Kit-Package\n", encoding="utf-8")
    assert rt.run_folder({"cwd": FOLDER}, "x", tmp_path) == FOLDER
    assert rt.run_folder(None, "make test", tmp_path) == ""
    assert rt.run_folder({"test": "x"}, "xcodebuild -workspace A.xcworkspace -scheme Kit-Package test", tmp_path) == ""
    assert rt.run_folder({"test": "x"}, "xcodebuild -scheme Kit-Package test", tmp_path) == FOLDER
    with pytest.raises(ValueError, match="relative folder inside the project"):
        rt.run_folder({"cwd": "../x"}, "x", tmp_path)


def test_missing_scheme_is_a_no_result_stop(tmp_path):
    fake = '#!/bin/sh\necho \'xcodebuild: error: The workspace named "App" does not contain a scheme named "Kit-Package".\'\nexit 65\n'
    project(tmp_path, {"language": "other", "test": "xcodebuild -scheme Kit-Package test", "isolate": False}, fake=fake)
    cp = go(tmp_path, "--full")
    assert cp.returncode == 1, cp.both
    assert "no tests ran: xcodebuild found no scheme or package in the project root" in cp.err
    summary = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert "no tests ran: xcodebuild found no scheme or package in the project root" in summary["error"]
    rows = incidents(tmp_path)
    assert not [r for r in rows if r.get("kind") == "test-failure"]
    no_result = [r for r in rows if r.get("kind") == "no-result"]
    assert len(no_result) == 1 and "scheme not found" in no_result[0]["target"]


def test_language_md_names_the_run_folder():
    text = (Path(__file__).resolve().parents[2] / "docs" / "language.md").read_text(encoding="utf-8")
    assert '"cwd"' in text and "package_scheme" in text


STALE = '<testsuite tests="1" failures="1"><testcase classname="a" name="t"><failure message="stale"/></testcase></testsuite>'


def test_relative_junit_resolves_in_the_run_folder(tmp_path):
    cfg = {"language": "other", "test": "echo 1 passed", "junit": "report.xml", "cwd": FOLDER, "isolate": False}
    project(tmp_path, cfg)
    stale = tmp_path / FOLDER / "report.xml"
    stale.write_text(STALE, encoding="utf-8")
    cp = go(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert not stale.exists()


def test_no_result_in_a_non_tree_folder_run_names_the_folder_not_a_cwd(tmp_path):
    cmd = "echo boom; exit 127"
    project(tmp_path, {"language": "other", "test": cmd, "cwd": FOLDER, "isolate": False})
    cp = go(tmp_path, "--full")
    assert cp.returncode == 2, cp.both
    rows = [r for r in incidents(tmp_path) if r.get("kind") == "no-result"]
    assert len(rows) == 1
    assert "cwd" not in rows[0] and FOLDER in rows[0]["context"]


def test_no_result_in_a_tree_folder_run_names_the_folder(tmp_path):
    cmd = "echo boom; exit 127"
    project(tmp_path, {"language": "other", "test": cmd, "test_file": cmd, "cwd": FOLDER, "isolate": True})
    plan = make_plan(tmp_path, [{"id": "T1", "owns": f"{FOLDER}/tests/a_test.sh"}], name="p.md")
    (tmp_path / FOLDER / "tests" / "a_test.sh").write_text("echo changed", encoding="utf-8")
    cp = go(tmp_path, "--fast", f"{FOLDER}/tests/a_test.sh", "--task", "T1", "--plan", str(plan))
    assert cp.returncode == 2, cp.both
    rows = [r for r in incidents(tmp_path) if r.get("kind") == "no-result"]
    assert len(rows) == 1
    assert FOLDER in json.dumps(rows[0]), rows[0]


def test_marker_files_are_relative_to_the_run_folder(tmp_path):
    out = tmp_path / "files.txt"
    cmd = f"echo {{files}} > {out}; pytest {{names}}"  # {names} with a path outside a test target: the resolved command is the plain test, so -m goes through marker_spec
    fake = "#!/bin/sh\necho 1 passed\n"
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "test_file": cmd, "cwd": FOLDER, "isolate": False}, fake=fake)
    (tmp_path / "bin" / "pytest").write_text(fake, encoding="utf-8")
    (tmp_path / "bin" / "pytest").chmod(0o755)
    cp = go(tmp_path, "-m", "slow", "--fast", f"{FOLDER}/Package.swift")
    assert cp.returncode == 0, cp.both
    assert out.read_text(encoding="utf-8") == "Package.swift\n"


def test_red_pytest_id_is_located_under_the_run_folder(tmp_path):
    out = "echo '___ test_x ___'; echo 'tests/a_test.py:3: AssertionError'; echo 'FAILED tests/a_test.py::test_x - boom'; echo '1 failed in 0.1s'; exit 1"
    project(tmp_path, {"language": "other", "test": out, "cwd": FOLDER, "isolate": False})
    (tmp_path / FOLDER / "tests" / "a_test.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a_test.py").write_text("# same name at the root\n", encoding="utf-8")
    cp = go(tmp_path, "--full")
    assert cp.returncode == 1, cp.both
    summary = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert list(summary["files"]) == [f"{FOLDER}/tests/a_test.py"], summary


def test_junit_file_attribute_is_stored_under_the_run_folder(tmp_path):
    xml = '<testsuite tests="1" failures="1"><testcase classname="k" name="t" file="tests/a_test.py"><failure message="bad"/></testcase></testsuite>'
    cmd = f"printf '%s' '{xml}' > {{junit}}; exit 1"
    project(tmp_path, {"language": "other", "test": cmd, "junit": "{junit}", "cwd": FOLDER, "isolate": False})
    (tmp_path / FOLDER / "tests" / "a_test.py").write_text("x\n", encoding="utf-8")
    cp = go(tmp_path, "--full")
    assert cp.returncode == 1, cp.both
    summary = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert list(summary["files"]) == [f"{FOLDER}/tests/a_test.py"], summary


def test_marker_with_a_bad_cwd_is_a_usage_error(tmp_path):
    cmd = "echo {files}; pytest {names}"
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "test_file": cmd, "cwd": "../outside", "isolate": False})
    cp = go(tmp_path, "-m", "slow", "--fast", f"{FOLDER}/Package.swift")
    assert cp.returncode == 2, cp.both
    assert "Traceback" not in cp.both


def test_marker_without_fast_defaults_come_from_the_run_folder(tmp_path):
    out = tmp_path / "files.txt"
    cmd = f"echo {{files}} > {out}; pytest"
    fake = "#!/bin/sh\necho 1 passed\n"
    project(tmp_path, {"language": "other", "test": "echo 1 passed", "test_file": cmd, "cwd": FOLDER, "isolate": False}, fake=fake)
    (tmp_path / "bin" / "pytest").write_text(fake, encoding="utf-8")
    (tmp_path / "bin" / "pytest").chmod(0o755)
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = elsewhere\n", encoding="utf-8")  # the root config must not hide the folder's own tests
    cp = go(tmp_path, "-m", "slow")
    assert cp.returncode == 0, cp.both
    assert out.read_text(encoding="utf-8") == "tests\n"
