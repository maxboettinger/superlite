"""run_tests --base-skips collects the files a skipped test's file names in SESSION_FILES, so a skip that depends on what its session collects matches the full run's (#1007)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import test_guard_parity as parity  # noqa: E402

COMPOSITE = '''from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
{decl}

def test_composite(request):
    collected = {{Path(str(i.path)).resolve() for i in request.session.items}}
    if all(p.resolve() in collected for p in HERE.glob("test_g_*.py")):
        pytest.skip("every companion runs in this session")


def test_plain():
    pass
'''
DECL = 'SESSION_FILES = ("test_g_*.py",)\n'
COMPANION = "def test_one():\n    pass\n"
SKIPPED = ["tests/test_p.py::test_composite"]
FULL = {"mode": "full", "started": 1763600000.5, "passed": 3, "failed": 0, "skipped": 1, "skipped_tests": SKIPPED}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "pytest.ini", "[pytest]\n")
    write(repo / "tests" / "test_p.py", COMPOSITE.format(decl=""))
    write(repo / "tests" / "test_g_1.py", COMPANION)
    write(repo / "tests" / "test_g_2.py", COMPANION)
    sd = repo / ".superlite"
    cmd = {"language": "python", "test": f"{sys.executable} -m pytest tests -q -rs -p no:cacheprovider",
           "test_file": f"{sys.executable} -m pytest {{files}} -q -p no:cacheprovider -o junit_family=xunit1 --junitxml={{junit}}", "junit": "{junit}"}
    write(sd / "test-cmd.json", json.dumps(cmd))
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    write(sd / "checkpoints.json", json.dumps({"base": base, "entries": []}))
    write(repo / "tests" / "test_p.py", COMPOSITE.format(decl=DECL))
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "declare")
    write(sd / "test-summary-full.json", json.dumps(FULL))
    return repo


def rt(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *args], cwd=repo, capture_output=True, text=True, timeout=180, env=env)


def test_declared_session_files_reads_only_a_literal_string_sequence(tmp_path):
    f = tmp_path / "test_x.py"
    cases = [
        ('SESSION_FILES = ("a.py", "test_*.py", "a.py")\n', ["a.py", "test_*.py"]),
        ('SESSION_FILES = ["b.py"]\n', ["b.py"]),
        ('SESSION_FILES: tuple = ("c.py",)\n', ["c.py"]),
        ('SESSION_FILES = ("old.py",)\nSESSION_FILES = ("new.py",)\n', ["new.py"]),
        ('BASE = ("a.py",)\nSESSION_FILES = BASE + ("b.py",)\n', []),
        ('SESSION_FILES = ("a.py", 3)\n', []),
        ('SESSION_FILES = "a.py"\n', []),
        ('def f():\n    SESSION_FILES = ("a.py",)\n', []),
        ('SESSION_FILES = (\n', []),
        ('OTHER = ("a.py",)\n', []),
    ]
    for text, want in cases:
        f.write_text(text, encoding="utf-8")
        assert run_tests.declared_session_files(f) == want, text
    assert run_tests.declared_session_files(tmp_path / "missing.py") == []
    for text in ("SESSION_FILES = " + "+".join(["1"] * 200000) + "\n", "SESSION_FILES = " + "-" * 100000 + "1\n"):
        f.write_text(text, encoding="utf-8")
        assert run_tests.declared_session_files(f) == []


def test_session_files_skip_unsafe_patterns_and_known_paths(tmp_path):
    root, tree = tmp_path / "root", tmp_path / "tree"
    write(root / "tests" / "test_p.py", 'SESSION_FILES = ("test_g_*.py", "test_x.py", "../outside.py", "/abs.py", "")\n')
    write(tree / "tests" / "test_p.py", 'SESSION_FILES = ("test_x.py", "sub/test_*.py", "test_dir")\n')
    for name in ("test_g_2.py", "test_g_1.py", "test_x.py", "sub/test_s.py", "test_other.py"):
        write(tree / "tests" / name, COMPANION)
    (tree / "tests" / "test_dir").mkdir()
    write(tree / "outside.py", COMPANION)
    write(tree / "tests" / "test_q.py", "")
    got = run_tests.session_files(root, tree, ["tests/test_p.py", "tests/test_g_2.py", "tests/test_q.py", "SwiftSuite"])
    assert got == ["tests/test_g_1.py", "tests/test_x.py", "tests/sub/test_s.py"]
    assert run_tests.session_files(root, tree, ["tests/test_q.py"]) == []
    assert run_tests.session_files(root, tree, ["tests/missing.py"]) == []


def test_base_run_collects_the_session_files_a_skipped_test_names(tmp_path):
    repo = make_repo(tmp_path)
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_tests: --base-skips: the base run also collects 2 files SESSION_FILES names, so a skip that depends on what its session collects matches the full run's" in r.stderr
    assert "run_tests: base " in r.stderr and " skips 1 of 1 of the full run's skipped tests" in r.stderr
    data = json.loads((repo / ".superlite" / "test-summary-base.json").read_text(encoding="utf-8"))
    assert data["compared"] == SKIPPED
    assert data["skipped_tests"] == SKIPPED
    assert (data["passed"], data["failed"], data["skipped"]) == (3, 0, 1)


def test_guard_parity_session_files_are_its_parity_files():
    own = "tests/scripts/test_guard_parity.py"
    assert run_tests.declared_session_files(ROOT / own) == list(parity.SESSION_FILES)
    want = [p.relative_to(ROOT).as_posix() for p in parity.parity_files()]
    assert run_tests.session_files(ROOT, ROOT, [own]) == want
    assert len(want) == len(set(want)) and own not in want
    assert want[:5] == [f"tests/scripts/{n}" for n in parity.SESSION_FILES[:5]]
