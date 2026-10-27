"""commit_task: hyphenated import roots, docs never block, one hint line, UTF-8-safe ledger."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (ENV, SCRIPTS, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

HY = "config/skills/reviewing-periods/scripts"
HEAD = "# P\n\n## 9. Implementation plan\n\n"


def task(n, owns, produces=""):
    out = f"### T{n} · t{n} · Complexity 2 · Est. context 10k · Est. time 1 min\n\n"
    out += "**Owns:** " + ", ".join(f"`{o}`" for o in owns) + "\n"
    if produces:
        out += f"**Produces:** {produces}\n"
    return out + "\n"


def repo_with(tmp_path, *tasks):
    repo = make_repo(tmp_path)
    (repo / "plan.md").write_text(HEAD + "".join(tasks), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def commit(repo, *args):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=ENV)


def hyphen_repo(tmp_path):
    files = [f"{HY}/review/__init__.py", f"{HY}/review/shell.py", f"{HY}/review/model.py"]
    repo = repo_with(tmp_path, task(1, files, "review.shell.run_json(argv: list[str]) -> dict"))
    write(repo, files[0], "")
    write(repo, files[2], "class X:\n    pass\n")
    write(repo, files[1], "from review.model import X\n\n\ndef run_json(argv):\n    return X\n")
    return repo


def test_hyphen_package_imports(tmp_path):
    repo = hyphen_repo(tmp_path)
    write(repo, ".superlite/test-cmd.json", json.dumps({"test": "pytest", "pythonpath": [HY]}))
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == git(repo, "rev-parse", "HEAD")
    assert "ModuleNotFoundError" not in r.stdout


def test_hyphen_package_derived_from_plan(tmp_path):
    repo = hyphen_repo(tmp_path)
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ModuleNotFoundError" not in r.stdout


def test_plain_src_import_unchanged(tmp_path):
    repo = repo_with(tmp_path, task(1, ["src/a.py", "src/b.py"]))
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "src/a.py", "from b import B\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr


def test_import_errors_roots_param(tmp_path, monkeypatch):
    write(tmp_path, "d-x/pkg/__init__.py", "")
    write(tmp_path, "d-x/pkg/m.py", "from pkg import nothing_here\n")
    monkeypatch.chdir(tmp_path)
    bad = commit_task.import_errors(["d-x/pkg/m.py"], ["d-x"])
    assert len(bad) == 1 and "ImportError" in bad[0][2]
    assert commit_task.import_errors([]) == []


def test_untracked_docs_not_blocking(tmp_path):
    repo = repo_with(tmp_path, task(1, ["src/a.py"]))
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "docs/spec.md", "s\n")
    write(repo, "docs/research/x.md", "x\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "out-of-scope" not in r.stdout and "hint:" not in r.stdout
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "src/a.py"
    st = git(repo, "status", "--porcelain", "--untracked-files=all")
    assert "?? docs/spec.md" in st and "?? docs/research/x.md" in st


def test_owned_doc_still_committed(tmp_path):
    repo = repo_with(tmp_path, task(1, ["docs/guide.md"]))
    write(repo, "docs/guide.md", "g\n")
    write(repo, "docs/other.md", "o\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "docs/guide.md"


def test_hint_once_for_two_tasks(tmp_path):
    repo = repo_with(tmp_path, task(1, ["src/a.py"]), task(2, ["src/b.py"]))
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "src/stray.py", "S = 1\n")
    r = commit(repo, "T1", "T2")
    lines = r.stdout.splitlines()
    assert lines.count("out-of-scope src/stray.py") == 2, r.stdout
    hint = "hint: commit or exclude these files, they are outside every Owns: src/stray.py"
    assert lines.count(hint) == 1, r.stdout
    assert sum(ln.startswith("hint:") for ln in lines) == 1


def test_ledger_with_ff_byte(tmp_path):
    repo = repo_with(tmp_path, task(1, ["src/a.py"]))
    write(repo, "src/a.py", "A = 1\n")
    led = repo / ".superlite" / "progress.md"
    led.parent.mkdir(exist_ok=True)
    led.write_bytes(b"# Progress ledger\n\n- Ruling: bad \xff byte\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert b"- commit T1 " in led.read_bytes()


def test_ruling_with_surrogate_written_utf8(tmp_path):
    repo = repo_with(tmp_path, task(1, ["src/a.py"]), task(2, ["src/b.py"]))
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    r = commit(repo, "T1", "--also", "src/b.py", "--ruling", "why \udcff here")
    assert r.returncode == 0, r.stdout + r.stderr
    text = (repo / ".superlite" / "progress.md").read_bytes().decode("utf-8")
    assert "why \ufffd here" in text
