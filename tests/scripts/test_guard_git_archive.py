"""Coordinator guard: git subcommands that rewrite project files and archive extraction into the project (#121)."""
import pytest

from test_block_coordinator_edits import bash, proj, run  # noqa: F401


@pytest.fixture
def tree(proj):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    (proj / "docs" / "plans").mkdir(parents=True)
    (proj / "docs" / "plans" / "p.md").write_text("x\n")
    return proj


@pytest.mark.parametrize("cmd", [
    "git checkout -- src/a.py",
    "git checkout HEAD -- src/a.py",
    "git checkout .",
    "git checkout HEAD~1 src/a.py",
    "git checkout src/a.py",
    "git checkout -f -- src",
    "git restore src/a.py",
    "git restore --source HEAD~1 src/a.py",
    "git restore --source=HEAD~1 -- src/a.py",
    "git restore -W -S src/a.py",
    "git restore .",
    "git restore ':/src/a.py'",
    "git restore --pathspec-from-file=/tmp/list",
    "cd src && git restore a.py",
    "git stash pop",
    "git stash apply",
    "git stash apply stash@{1}",
    "git stash branch fix",
    "git reset --hard",
    "git reset --hard HEAD~1",
    "git reset --merge ORIG_HEAD",
    "git reset --keep HEAD~1",
    "git rm src/a.py",
    "git rm -r src",
    "git mv src/a.py src/b.py",
    "git mv docs/plans/p.md src/p.md",
    "git clean -fd",
    "git clean -fd src",
    "git clean -fdx -e .env",
    "git -c core.pager=cat checkout -- src/a.py",
    "tar -C src -xf /tmp/x.tar",
    "tar -xf /tmp/x.tar",
    "tar xf /tmp/x.tar -C src",
    "tar xvzf /tmp/x.tgz",
    "tar --extract --file=/tmp/x.tar --directory=src",
    "tar -xzf /tmp/x.tgz --directory src",
    "tar -xPf /tmp/x.tar -C /tmp/out",
    "bsdtar -xf /tmp/x.tar",
    "unzip -d src /tmp/x.zip",
    "unzip /tmp/x.zip",
    "unzip -o /tmp/x.zip -d src",
    "unzip -q /tmp/x.zip -dsrc",
])
def test_rewrites_of_project_files_block(tree, cmd):
    assert bash(tree, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    "git checkout main",
    "git checkout -b feature",
    "git checkout -B feature origin/main",
    "git switch main",
    "git checkout -- docs/plans/p.md",
    "git restore docs/plans/p.md .superlite/fixes/F.md",
    "git restore --staged src/a.py",
    "git restore -S src/a.py",
    "git rm --cached src/a.py",
    "git rm -n src/a.py",
    "git mv docs/plans/p.md docs/plans/q.md",
    "git clean -n",
    "git clean -fd .superlite/tmp",
    "cd .superlite && git clean -fd",
    "git reset HEAD src/a.py",
    "git reset --soft HEAD~1",
    "git reset",
    "git stash",
    "git stash list",
    "git stash show -p",
    "git stash drop",
    "git merge feature",
    "git pull",
    "git status && git diff && git log -1",
    "git -C /tmp/other restore src/a.py",
    "git -C /tmp/other stash pop",
    "git -C /tmp/other reset --hard",
    "tar -cf /tmp/x.tar src",
    "tar -tf /tmp/x.tar",
    "tar -xf /tmp/x.tar -C /tmp/out",
    "tar -xf /tmp/x.tar -C .superlite/fixes",
    "unzip -l /tmp/x.zip",
    "unzip -d /tmp/out /tmp/x.zip",
    "unzip -p /tmp/x.zip a.txt",
])
def test_reads_branch_moves_and_allowed_targets_pass(tree, cmd):
    assert bash(tree, cmd).returncode == 0, cmd


def test_outside_the_project_relative_paths_are_not_project_code(tree, tmp_path_factory):
    out = tmp_path_factory.mktemp("elsewhere")
    for cmd in ("git restore src/a.py", "git stash pop", "git reset --hard", "tar -xf /tmp/x.tar", "unzip /tmp/x.zip"):
        assert run(tree, "Bash", {"command": cmd}, cwd=str(out)).returncode == 0, cmd
    assert run(tree, "Bash", {"command": f"git -C {tree} restore src/a.py"}, cwd=str(out)).returncode == 2
    assert run(tree, "Bash", {"command": f"tar -xf /tmp/x.tar -C {tree}/src"}, cwd=str(out)).returncode == 2


def test_outside_a_run_only_protected_files_block(tmp_path):
    (tmp_path / ".superlite").mkdir()
    for cmd in ("git checkout -- src/a.py", "git stash pop", "git reset --hard", "git clean -fd", "tar -xf /tmp/x.tar"):
        assert bash(tmp_path, cmd).returncode == 0, cmd
    assert bash(tmp_path, "git checkout -- .superlite/orchestrator.json").returncode == 2


def test_hooks_doc_names_git_and_archive_rules():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text()
    line = [x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`")][0]
    for s in ("`stash pop|apply|branch`", "branch moves", "`tar -x` and `unzip`", "other archivers"):
        assert s in line, s
