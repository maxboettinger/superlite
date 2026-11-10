"""rm -r / rmdir of a folder that holds only untracked, unowned files passes; every block names the one command it refused (#421)."""
import io
import json
import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402

PLAN = "# Plan\n\n### T1 a\n**Owns:** src/a.py, tests/owned/\n\n### T2 b\n**Owns:** gen/sub/keep.py\n"


def git(P, *a):
    subprocess.run(["git", "-C", str(P), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True,
                   capture_output=True)


@pytest.fixture
def P(tmp_path):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "docs" / "plans").mkdir(parents=True)
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(PLAN)
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / "lib" / "x").mkdir(parents=True)
    (p / "lib" / "x" / "t.py").write_text("t = 1\n")
    (p / ".gitignore").write_text("__pycache__/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def j(P, cmd, mode="active"):
    return gj.judge(cmd, cwd=str(P), project=str(P), mode=mode, sds=(str(P / ".superlite"),))


def tree(P, rel, files=("f.txt",)):
    d = P / rel
    d.mkdir(parents=True, exist_ok=True)
    for f in files:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text("x")
    return d


def test_rm_r_untracked_unowned_folder_passes(P):
    tree(P, "tests/regression", ("test_x.py", "__pycache__/test_x.cpython-312.pyc"))
    for cmd in ("rm -r tests/regression", "rm -rf tests/regression", "rm -R tests/regression",
                "rm -r tests/regression/", "cd tests && rm -r regression"):
        assert j(P, cmd) is None, cmd


def test_rmdir_empty_untracked_folder_passes(P):
    (P / "tests" / "regression" / "__pycache__").mkdir(parents=True)
    assert j(P, "rmdir tests/regression/__pycache__") is None
    assert j(P, "rm -d tests/regression/__pycache__") is None


def test_rm_r_folder_with_a_tracked_file_blocks(P):
    (P / "src" / "new_untracked.py").write_text("x")
    for cmd, rel in (("rm -r src", "src"), ("rm -r lib", "lib"), ("rmdir lib/x", "lib/x")):
        v = j(P, cmd)
        assert v is not None and v.kind == "code" and v.rel == rel, cmd


def test_rm_r_owned_folder_blocks(P):
    tree(P, "tests/owned")
    tree(P, "gen/sub", ("other.txt",))
    for cmd in ("rm -r tests/owned", "rm -r tests", "rm -r gen", "rm -r gen/sub"):
        v = j(P, cmd)
        assert v is not None and v.kind == "code", cmd


def test_rm_r_folder_blocks_on_any_doubt(P):
    os.symlink(P / "src" / "a.py", tree(P, "tmp/links") / "l")
    os.link(P / "src" / "a.py", tree(P, "tmp/hard") / "h")
    tree(P, "tmp/repo/.git", ("HEAD",))
    tree(P, "tmp/run/.superlite", ("pool.json",))
    tree(P, "tmp/named", ("orchestrator.json",))
    tree(P, "tmp/big", [f"f{i}" for i in range(2001)])
    for rel in ("tmp/links", "tmp/hard", "tmp/repo", "tmp/run", "tmp/named", "tmp/big"):
        v = j(P, f"rm -r {rel}")
        assert v is not None and v.kind == "code", rel


def test_rm_r_git_or_run_folder_itself_blocks(P):
    subprocess.run(["git", "init", "-q", str(P / "tmp" / "repo")], check=True)
    for cmd in ("rm -r .git", "rm -r .superlite", "rm -r tmp/repo/.git"):
        v = j(P, cmd)
        assert v is not None and v.kind in ("code", "protected"), cmd


def test_rm_r_folder_other_doubts_block(P):
    tree(P, "tmp/a")
    assert j(P, "rm -r tmp/a", mode="human").kind == "human"
    for cmd in ("rm -r tmp/*", "rm -r $X", "cd $X && rm -r tmp/a", "unlink tmp/a"):
        v = j(P, cmd)
        assert v is not None and v.kind == "code", cmd
    (P / ".superlite" / "stable.json").unlink()
    assert j(P, "rm -r tmp/a").kind == "code"


def test_file_rule_unchanged(P):
    (P / "stray.txt").write_text("x")
    assert j(P, "rm stray.txt") is None
    assert j(P, "rm src/a.py").kind == "code"


def test_owns_within_examples():
    assert gj._owns_within("gen", ["gen/sub/keep.py"]) is True
    assert gj._owns_within("tests/regression", ["src/a.py", "tests/owned/"]) is False
    assert gj._owns_within("tests", ["tests/**/test_*.py"]) is True
    assert gj._owns_within("tests/owned/x", ["tests/owned/"]) is True
    assert gj._owns_within("src/sub", ["src/*.py"]) is True


def test_tree_ok(tmp_path):
    assert gj._tree_ok(str(tmp_path)) is True
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f").write_text("x")
    assert gj._tree_ok(str(tmp_path)) is True
    (tmp_path / "a" / "Backlog.JSON").write_text("x")
    assert gj._tree_ok(str(tmp_path)) is False
    assert gj._tree_ok(str(tmp_path / "missing")) is False


def run_main(P, monkeypatch, capsys, command):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(P)})))
    rc = gj.main(["--mode", "active", "--project", str(P), "--sd", str(P / ".superlite")])
    return rc, capsys.readouterr().err.splitlines()


def refused(lines):
    return [ln for ln in lines if ln.startswith("Refused command: ")]


def test_block_names_the_one_refused_command(P, monkeypatch, capsys):
    rc, lines = run_main(P, monkeypatch, capsys, "echo a && rm -r src && echo b")
    assert rc == 2
    assert refused(lines) == [gj.REFUSED.format("rm -r src")]
    assert lines[-2:] == [f"Absolute target: {P}/src", "Blocked target: src"]
    assert lines.index(refused(lines)[0]) == len(gj.MESSAGES["code"])


def test_refused_command_names_a_redirect(P, monkeypatch, capsys):
    rc, lines = run_main(P, monkeypatch, capsys, "echo ok; echo hi > src/a.py; echo done")
    assert rc == 2 and refused(lines) == [gj.REFUSED.format("echo hi > src/a.py")]
    assert lines[-1] == "Blocked target: src/a.py"


def test_refused_command_is_the_innermost(P, monkeypatch, capsys):
    rc, lines = run_main(P, monkeypatch, capsys, "echo a && bash -c 'rm -r src'")
    assert rc == 2 and refused(lines) == [gj.REFUSED.format("rm -r src")]
    assert j(P, "echo a && rm -r src && echo b").cmd == "rm -r src"


def test_refused_line_keeps_the_last_lines(P, monkeypatch, capsys):
    rc, lines = run_main(P, monkeypatch, capsys, "echo a && rm $(cat list)")
    assert rc == 2 and len(refused(lines)) == 1 and refused(lines)[0].startswith("Refused command: rm ")
    assert lines[-3] == gj.UNRESOLVED_HINT and lines[-2].startswith("Unresolved word: ")
    assert lines[-1].startswith("Blocked command: ")
    assert lines.index(refused(lines)[0]) < len(lines) - 3


def test_protected_block_names_the_command(P, monkeypatch, capsys):
    rc, lines = run_main(P, monkeypatch, capsys, "echo a; echo x > .superlite/orchestrator.json")
    assert rc == 2 and refused(lines) == [gj.REFUSED.format("echo x > .superlite/orchestrator.json")]
    assert not any(ln.startswith("Blocked target") for ln in lines)
