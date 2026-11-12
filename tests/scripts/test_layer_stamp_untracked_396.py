"""#396: the unit stamp hashes untracked files, so committing them (autocommit apply) keeps it green."""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_autocommit import SCRIPTS, ENV, make_repo, write, git, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402

TOP = Path(__file__).resolve().parents[2]


def layers(repo, *args, state):
    env = {**ENV, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(repo / "scripts" / "test_layers.py"), *args, "--state", str(state)],
                          cwd=repo, capture_output=True, text=True, env=env, encoding="utf-8")


def layer_repo(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "scripts").mkdir()
    for name in ("test_layers.py", "layer_store.py"):
        shutil.copy(TOP / "scripts" / name, repo / "scripts" / name)
    write(repo, ".gitignore", "__pycache__/\n*.pyc\n")
    write(repo, "skills/x/scripts/a.py", "a = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "layers")
    return repo


def batch(repo, monkeypatch):
    write(repo, "skills/x/scripts/a.py", "a = 2\n")
    write(repo, "tests/scripts/test_new.py", "def test_new():\n    assert True\n")
    monkeypatch.chdir(repo)
    autocommit.checkpoint("T1", "new test", ["skills/x/scripts/a.py", "tests/scripts/test_new.py"], "plan.md")


def test_untracked_test_file_is_in_the_unit_stamp(tmp_path, monkeypatch):
    repo = layer_repo(tmp_path)
    state = tmp_path / "layers.json"
    batch(repo, monkeypatch)
    assert "tests/scripts/test_new.py" in git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    assert layers(repo, "stamp", "unit", "--ruling", "r", state=state).returncode == 0
    write(repo, "tests/scripts/test_new.py", "def test_new():\n    assert 1\n")
    r = layers(repo, "check", state=state)
    assert r.returncode == 2
    assert "unit stale: tests/scripts/test_new.py" in r.stdout


def test_unit_stamp_stays_green_across_autocommit_apply(tmp_path, monkeypatch):
    repo = layer_repo(tmp_path)
    state = tmp_path / "layers.json"
    batch(repo, monkeypatch)
    assert layers(repo, "stamp", "unit", "--ruling", "r", state=state).returncode == 0
    before = layers(repo, "status", state=state).stdout
    assert before.startswith("unit stamped ")
    r = run("autocommit", "apply", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tests/scripts/test_new.py" in git(repo, "ls-files").splitlines()
    assert layers(repo, "status", state=state).stdout == before
    assert layers(repo, "check", state=state).returncode == 0
