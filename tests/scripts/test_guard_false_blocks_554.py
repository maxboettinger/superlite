"""Guard false blocks (#554): read-only git apply, argv tuple unpack, f-string targets."""
from test_block_coordinator_edits import bash, proj  # noqa: F401


def test_git_apply_check_reads_only(proj):
    pre = "D=/tmp/x; git diff HEAD --binary > $D/b.patch; "
    assert bash(proj, pre + "git apply --check -R $D/b.patch").returncode == 0
    assert bash(proj, "git apply x.patch").returncode == 2


def test_argv_tuple_unpack(proj):
    body = "import sys\np,img=sys.argv[1],sys.argv[2]\nopen(p,'w').write('x')\nEOF"
    cmd = 'S=/tmp/sc; python3 -I - "$S/copy/A.swift" "$S/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd).returncode == 0
    cmd2 = 'python3 -I - "src/A.swift" "/tmp/sc/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd2).returncode == 2


def test_fstring_with_unknown_piece_stays_blocked(proj):
    def code(target: str) -> str:
        return "python3 - <<'EOF'\nfrom pathlib import Path\nx='../../src/a'\n" + target + ".write_text(x)\nEOF"

    assert bash(proj, code('Path(f".superlite/plan-parts/{letter}.md")')).returncode == 2
    assert bash(proj, code('Path(f"src/{n}.py")')).returncode == 2
    assert bash(proj, code("Path(f'.superlite/plan-parts/{x}')")).returncode == 2


def test_pins_that_pass_today(proj):
    note = 'echo "Left undone: x" >> .superlite/notes.md; python3 - <<\'EOF\'\nimport json\nprint(json.load(open("docs/plans/a.json")))\nEOF'
    assert bash(proj, note).returncode == 0
    assert bash(proj, "python3 -I - <<EOF\nimport json\nprint(json.load(open('docs/plans/a.json')))\nEOF").returncode == 0


def test_fstring_glob_directly_below_superlite_root_blocks(proj):
    bad = "python3 - <<'EOF'\nimport sys\nfrom pathlib import Path\nx = sys.argv[1]\nPath(f\".superlite/{x}\").write_text('a')\nEOF"
    assert bash(proj, bad).returncode == 2


# --- #664: a git-ignored, unowned path passes as an rm target and as a write target ----------------------------
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_judge as gj  # noqa: E402

PLAN_664 = "# Plan\n\n### T1 a\n**Owns:** src/a.py, .build/owned/\n\n### T2 b\n**Owns:** lib/b.py\n"


def _git(p, *a):
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


@pytest.fixture
def G(tmp_path):
    p = (tmp_path / "proj").resolve()
    (p / "src").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "docs" / "plans").mkdir(parents=True)
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(PLAN_664)
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / ".gitignore").write_text(".build/\n*.log\ntmp/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    _git(p, "add", "-A")
    _git(p, "commit", "-q", "-m", "init")
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def jg(G, cmd, cwd=None):
    return gj.judge(cmd, cwd=str(cwd or G), project=str(G), mode="active", sds=(str(G / ".superlite"),))


def _files(d, n):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"f{i}").write_text("x")
    return d


def test_rm_ignored_folder_of_2100_files_passes(G):
    _files(G / ".build" / "dd", 2100)
    os.symlink(G / "src" / "a.py", G / ".build" / "dd" / "link")
    os.link(G / "src" / "a.py", G / ".build" / "dd" / "hard")
    for cmd in ("rm -rf .build/dd", "rm -r .build/dd/", "cd .build && rm -rf dd", "rmdir .build/dd"):
        assert jg(G, cmd) is None, cmd
    assert jg(G, "rm .build/dd/hard") is None  # one name of a hard-linked file
    assert jg(G, "unlink .build/dd/f1") is None
    _files(G / "tmp" / "x", 3)
    assert jg(G, "rm -rf tmp") is None


def test_rm_ignored_owned_path_blocks(G):
    _files(G / ".build" / "owned", 3)
    for cmd in ("rm -rf .build/owned", "rm -rf .build"):
        v = jg(G, cmd)
        assert v is not None and v.kind == "code" and v.why == "owned by task T1", cmd


def test_rm_untracked_not_ignored_folder_of_2100_files_blocks(G):
    _files(G / "untr", 2100)
    v = jg(G, "rm -rf untr")
    assert v is not None and v.kind == "code" and v.rel == "untr"
    assert v.why == "not git-ignored; more than 2000 entries"


def test_untracked_not_ignored_folder_reasons(G):
    os.symlink(G / "src" / "a.py", _files(G / "t1", 1) / "l")
    os.link(G / "src" / "a.py", _files(G / "t2", 1) / "h")
    v1, v2 = jg(G, "rm -r t1"), jg(G, "rm -r t2")
    assert v1.kind == "code" and v1.why.startswith("not git-ignored; symlink")
    assert v2.kind == "code" and v2.why.startswith("not git-ignored; hard link")
    assert jg(G, "rm -r src").why == "tracked by git"


def test_redirect_tee_cp_mv_into_ignored_folder_pass(G):
    (G / ".build").mkdir()
    (G / ".build" / "old.log").write_text("x")
    for cmd in ("echo hi > .build/x.log", "xcodebuild test > .build/new/b.log 2>&1", "echo hi | tee .build/t.log",
                "cp src/a.py .build/copy.py", "mv .build/old.log .build/older.log", "echo hi >> run.log",
                "cd .build && echo hi > here.txt"):
        assert jg(G, cmd) is None, cmd


def test_writes_keep_their_blocks(G):
    (G / ".build").mkdir()
    os.link(G / "src" / "a.py", G / ".build" / "hard.log")
    v = jg(G, "echo hi > .build/hard.log")  # a write through a hard link reaches src/a.py
    assert v is not None and v.kind == "code"
    v = jg(G, "echo hi > src/new.py")
    assert v is not None and v.rel == "src/new.py" and v.why == "not git-ignored"
    v = jg(G, "echo hi > src/a.py")
    assert v is not None and v.rel == "src/a.py" and v.why == "tracked by git"
    _files(G / ".build" / "owned", 1)
    v = jg(G, "cp src/a.py .build/owned/f0")
    assert v is not None and v.why == "owned by task T1"
    v = jg(G, "echo hi > .build/*.log")  # a glob target: not housekeeping
    assert v is not None


def test_ignored_folder_holding_a_worktree_blocks(G):
    _git(G, "worktree", "add", "-q", str(G / "tmp" / "wts" / "wt"))
    for cmd in ("rm -rf tmp", "rm -rf tmp/wts", "rm -rf tmp/wts/wt"):
        v = jg(G, cmd)
        assert v is not None and v.why == "holds the linked worktree tmp/wts/wt", cmd
    v = jg(G, "echo hi > tmp/wts/wt/src/a.py")  # tracked in that worktree
    assert v is not None and v.why == "tracked by git"
    assert jg(G, "echo hi > tmp/wts/wt/build.log") is None  # ignored in that worktree too


def test_ignored_folder_holding_the_state_folder_blocks(G):
    sd = _files(G / "tmp" / "state", 1)
    v = gj.judge("rm -rf tmp", cwd=str(G), project=str(G), mode="active", sds=(str(G / ".superlite"), str(sd)))
    assert v is not None and v.why == "holds the run's state folder"


def test_git_and_run_paths_keep_their_rules(G):
    _git(G, "init", "-q", str(G / ".build" / "repo"))
    v = jg(G, "rm -rf .build/repo/.git")
    assert v is not None and v.why == ".git, .superlite and run files keep their own rules"
    assert jg(G, "rm -rf .build/repo") is None  # a nested repository under an ignored folder is build output


def test_no_plan_no_housekeeping(G):
    _files(G / ".build" / "dd", 1)
    (G / ".superlite" / "stable.json").unlink()
    v = jg(G, "rm -rf .build/dd")
    assert v is not None and v.why == "no run plan to read Owns from"


def test_block_prints_why_after_the_refused_line(G, monkeypatch, capsys):
    _files(G / ".build" / "owned", 1)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf .build/owned"}, "cwd": str(G)})))
    rc = gj.main(["--mode", "active", "--project", str(G), "--sd", str(G / ".superlite")])
    lines = capsys.readouterr().err.splitlines()
    assert rc == 2
    k = lines.index(gj.REFUSED.format("rm -rf .build/owned"))
    assert lines[k + 1] == "Not housekeeping: owned by task T1"
    assert lines[-2:] == [f"Absolute target: {G}/.build/owned", "Blocked target: .build/owned"]
