"""#1161: a later redirect to a git-ignored file that only earlier redirects of the same Bash call wrote passes as
housekeeping; any other write of that file, or of a folder above it, anywhere in the call keeps the block."""
import json, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402

WROTE = "below a path this command wrote earlier"
OTHER = "a path another command of this call writes too"
SIGHTING = "make record-fixtures > build/verify-record.log 2>&1; echo record exit $? >> build/verify-record.log"


def git(P, *a):
    subprocess.run(["git", "-C", str(P), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True,
                   capture_output=True)


@pytest.fixture
def P(tmp_path):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / "docs" / "plans").mkdir(parents=True)
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text("# Plan\n\n### T1 a\n**Owns:** src/a.py\n")
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / "src" / "c.py").write_text("x = 2\n")
    (p / ".gitignore").write_text("build/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    (p / "build").mkdir()
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


@pytest.fixture
def D(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "f.txt").write_text("plain\n")
    return d


def j(P, cmd, mode="active"):
    return gj.judge(cmd, cwd=str(P), project=str(P), mode=mode, sds=(str(P / ".superlite"),))


def test_sighting_parts_pass_alone(P):
    assert j(P, "make record-fixtures") is None
    assert j(P, "make record-fixtures > build/verify-record.log 2>&1") is None


@pytest.mark.parametrize("cmd", [
    SIGHTING,
    "echo a > build/x.log; echo b >> build/x.log; echo c >> build/x.log",
    "echo a > build/x.log 2>&1 && echo b >> build/x.log || echo c >> build/x.log",
    "echo a >> build/x.log; echo b > build/x.log",
    "echo a > build/x.log; echo b 2>> build/x.log",
    "echo a &> build/x.log; echo b &>> build/x.log",
    "echo a > build/x.log; cd build; echo b >> x.log",
    "echo a > build/x.log; (echo b >> build/x.log)",
    "echo a > build/x.log; for i in 1 2; do echo $i >> build/x.log; done",
    "LOG=build/x.log; echo a > \"$LOG\"; echo b >> \"$LOG\"",
])
def test_repeat_redirect_passes(P, cmd):
    assert j(P, cmd) is None, cmd


def test_earlier_other_write_keeps_old_text(P):
    v = j(P, "cp src/a.py build/x.log; echo b >> build/x.log")
    assert v is not None and v.kind == "code" and v.why == WROTE, v


def test_link_between_redirects_blocks(P):
    v = j(P, "echo a > build/x.log; ln -sf ../src/a.py build/x.log; echo b >> build/x.log")
    assert v is not None and v.kind == "code", v


def test_other_write_after_reuse_blocks(P, D):
    assert j(P, f"cp -R {D}/. build/") is None
    v = j(P, f"echo a > build/x.log; echo b >> build/x.log; cp -R {D}/. build/")
    assert v is not None and v.kind == "code" and v.why == OTHER, v


def test_other_write_in_loop_blocks(P, D):
    v = j(P, f"echo a > build/x.log; for i in 1 2; do echo $i >> build/x.log; cp -R {D}/. build/; done")
    assert v is not None and v.kind == "code", v


def test_tracked_file_still_blocks(P):
    v = j(P, "echo a > src/c.py; echo b >> src/c.py")
    assert v is not None and v.kind == "code", v


def test_different_files_unchanged(P):
    assert j(P, "echo a > build/a.log; echo b >> build/b.log") is None


def test_no_run_plan_still_blocks(P):
    (P / ".superlite" / "stable.json").unlink()
    v = j(P, SIGHTING)
    assert v is not None and v.kind == "code", v
