"""#639: `sl backlog ship lock` says whether the sync changed the tree."""
import subprocess
import pytest
from test_backlog_ship import sh, ship, AG  # noqa: F401
import backlog_ship as bsh

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@e"]


def g(cwd, *args):
    return subprocess.run(GIT + list(args), cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def put(cwd, rel, text="x\n"):
    p = cwd / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    g(cwd, "add", rel)
    g(cwd, "commit", "-m", rel)


@pytest.fixture
def real(sh, tmp_path, monkeypatch):
    """The sh fixture with its worktree a real clone (branch feat, unpushed) of a bare origin."""
    origin, seed = tmp_path / "origin.git", tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(origin), str(seed)], check=True, capture_output=True)
    g(seed, "checkout", "-b", "main")
    put(seed, "a.txt")
    g(seed, "push", "origin", "main")
    subprocess.run(["rm", "-rf", str(sh.wt)], check=True)
    subprocess.run(["git", "clone", str(origin), str(sh.wt)], check=True, capture_output=True)
    g(sh.wt, "checkout", "-b", "feat")
    put(sh.wt, "f.txt")
    sh.seed = seed

    def run(cmd, cwd, timeout=None):
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    monkeypatch.setattr(bsh, "_run", run)
    return sh


def move_origin(real, *files):
    for f in files:
        put(real.seed, f)
    g(real.seed, "push", "origin", "main")


def test_lock_prints_tree_unchanged(real, capsys):
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and out == "TREE: unchanged by the sync: the tested tree ships, no full rerun\nB1 lock held\n"


def test_lock_tree_changed_names_rerun(real, capsys):
    move_origin(real, "docs/x.md", "src/a.py")
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and out.splitlines()[0] == "TREE: changed by the sync (2 files: docs/x.md, src/a.py): run the full suite once (sl run_tests --full) before bump"


def test_lock_not_code_change(real, capsys):
    (real.wt / ".superlite").mkdir(exist_ok=True)
    (real.wt / ".superlite" / "test-cmd.json").write_text('{"test": "true", "not_code": ["docs/**"]}')
    move_origin(real, "docs/x.md")
    assert ship(capsys, "B1", "lock")[1].splitlines()[0] == "TREE: changed by the sync only in not-code paths (1 file): no full rerun"


def test_no_tree_line_with_layer_checker(sh, capsys):
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and "TREE:" not in out


def test_tree_line_lists_five(real):
    before = g(real.wt, "rev-parse", "HEAD^{tree}")
    move_origin(real, *[f"s/f{i}.py" for i in range(7)])
    g(real.wt, "fetch", "origin")
    g(real.wt, "rebase", "origin/main")
    line = bsh.tree_line(real.wt, before)
    assert "(7 files: s/f0.py, s/f1.py, s/f2.py, s/f3.py, s/f4.py, +2 more)" in line


def test_no_line_without_before(real):
    assert bsh.tree_line(real.wt, "") is None
