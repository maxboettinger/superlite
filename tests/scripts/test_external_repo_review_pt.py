"""Review regressions for plan_tools external (B48 T2)."""
from __future__ import annotations

import time

from test_external_repo_cmd import PY, ext, git, plan_file, shared_repo, tree_of
from test_plan_tools import PLAN_TOOLS, run


def test_commit_non_ascii_owned_path(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    text = p.read_text(encoding="utf-8").replace("src/helper.py, tests/test_helper.py", "src/hélper.py, src/other.py")
    p.write_text(text, encoding="utf-8")
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "hélper.py").write_text("Y = 2\n", encoding="utf-8")
    cp = ext(p, "T1", "--commit")
    assert cp.returncode == 0, cp.stderr
    assert "left uncommitted" not in cp.stderr
    assert "hélper.py" in git(tree, "-c", "core.quotepath=false", "show", "--name-only", "--format=", "HEAD")


def test_test_timeout_with_child_returns(tmp_path):
    cmd = f"{PY} -c \"import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(8)']); time.sleep(8)\""
    cmd = cmd.replace("sys; sub", "sys,time; sub")
    p = plan_file(tmp_path, shared_repo(tmp_path), test=cmd)
    t0 = time.time()
    cp = ext(p, "T1", "--test", "--timeout", "1")
    assert time.time() - t0 < 6
    assert cp.returncode == 1
    assert "timeout after 1s" in cp.stdout


def test_tree_with_spaces_is_quoted_in_ship(tmp_path):
    root = shared_repo(tmp_path)
    spaced = tmp_path / "my plans"
    spaced.mkdir()
    p = plan_file(spaced, root)
    cp = ext(p, "T1")
    assert cp.returncode == 0, cp.stderr
    ship = [ln for ln in cp.stdout.splitlines() if ln.startswith("ship: ")][0]
    assert "'" in ship and "my plans" in ship


def test_lint_empty_repo_value(tmp_path):
    p = plan_file(tmp_path, shared_repo(tmp_path))
    text = p.read_text(encoding="utf-8").replace(f"**Repo:** {tmp_path / 'shared'}", "**Repo:**")
    p.write_text(text, encoding="utf-8")
    cp = run(PLAN_TOOLS, "lint", "--plan", str(p))
    assert "**Repo:** line is empty" in cp.both
    assert "is this repository" not in cp.both
