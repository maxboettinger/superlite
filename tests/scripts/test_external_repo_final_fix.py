from __future__ import annotations

import shutil
import sys

from test_external_repo_cmd import ext, git, plan_file, shared_repo, tree_of
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools as pt  # noqa: E402


def test_prepare_after_tree_folder_deleted(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    tree = tree_of(ext(p, "T1"))
    shutil.rmtree(tree)
    cp = ext(p, "T1")
    assert cp.returncode == 0, cp.stderr
    assert (tree / ".git").exists()


def test_commit_glob_named_outside_file_does_not_unstage_owned(tmp_path):
    root = shared_repo(tmp_path)
    p = plan_file(tmp_path, root)
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "helper.py").write_text("X = 2\n", encoding="utf-8")
    (tree / "*").write_text("scratch\n", encoding="utf-8")
    cp = ext(p, "T1", "--commit")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert git(tree, "show", "--name-only", "--format=", "HEAD").splitlines() == ["src/helper.py"]


def test_plan_path_with_spaces_quoted_in_then_and_brief(tmp_path):
    root = shared_repo(tmp_path)
    spaced = tmp_path / "my plans"
    spaced.mkdir()
    p = plan_file(spaced, root)
    tree = tree_of(ext(p, "T1"))
    (tree / "src" / "helper.py").write_text("X = 2\n", encoding="utf-8")
    cp = ext(p, "T1", "--commit")
    then = [ln for ln in cp.stdout.splitlines() if ln.startswith("then: ")][0]
    assert f"--plan '{p}' --done" in then
    shutil.rmtree(tree)
    cp = ext(p, "T1", "--commit")
    assert f"--plan '{p}' first" in cp.stderr
    plan = pt.Plan.load(str(p))
    brief = "\n".join(pt.external_brief(str(p), plan.by_id["T1"]))
    assert brief.count(f"--plan '{p}'") == 2
