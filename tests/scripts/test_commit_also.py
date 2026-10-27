"""commit_task --also FILE --ruling TEXT, and the ticket key in commit messages."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (SCRIPTS, ENV, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402

OFF = {**ENV, "SUPERLITE_AUTOCOMMIT": "0"}
RULING = "protocol change breaks the double"


def commit(repo, *args, env=ENV):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=env)


def files_of(repo, rev="HEAD"):
    return sorted(git(repo, "show", "--name-only", "--format=", rev).split())


def ledger(repo):
    p = repo / ".superlite" / "progress.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def with_ticket(repo, key="PIX-1277"):
    p = repo / "plan.md"
    p.write_text(p.read_text(encoding="utf-8").replace("# Fixture plan\n", f"# Fixture plan\n\n**Ticket:** {key}\n", 1),
                 encoding="utf-8")


def test_also_commits_other_tasks_file(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")  # owned by T2
    r = commit(repo, "T1", "--also", "src/b.py", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_of(repo) == ["src/a.py", "src/b.py"]


def test_also_commits_unowned_file(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "Tests/Doubles/Fake.txt", "fake\n")
    r = commit(repo, "T1", "--also", "Tests/Doubles/Fake.txt", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_of(repo) == ["Tests/Doubles/Fake.txt", "src/a.py"]


def test_also_unchanged_file_noted_and_ignored(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1", "--also", "README.md", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "README.md" in r.stderr and "unchanged" in r.stderr
    assert files_of(repo) == ["src/a.py"]
    assert "Ruling" not in ledger(repo)


def test_also_needs_one_task_and_ruling(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "x.txt", "x\n")
    r = commit(repo, "T1", "T2", "--also", "x.txt", "--ruling", RULING)
    assert r.returncode == 2 and "error: --also takes exactly one task" in r.stderr
    r = commit(repo, "T1", "--also", "x.txt")
    assert r.returncode == 2 and "--ruling" in r.stderr
    assert git(repo, "rev-list", "--count", "HEAD") == "1"


def test_ruling_line_written(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "x.txt", "x\n")
    r = commit(repo, "T1", "--also", "x.txt", "--ruling", RULING, "--ledger", "led.md")
    assert r.returncode == 0, r.stdout + r.stderr
    text = (repo / "led.md").read_text(encoding="utf-8")
    assert f"- Ruling: T1 also commits x.txt - {RULING}" in text


def test_checkpoint_message_has_ticket(tmp_path):
    repo = make_repo(tmp_path)
    with_ticket(repo)
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1", env=OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "log", "-1", "--format=%s", r.stdout.strip()) == "PIX-1277 T1: parser"
    st = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert st["entries"][-1]["title"] == "PIX-1277 T1: parser"


def test_real_commit_message_has_ticket(tmp_path):
    repo = make_repo(tmp_path)
    with_ticket(repo)
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "log", "-1", "--format=%s") == "PIX-1277 T1: parser"


def test_message_and_ticket_unit(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("# P\n\n**Ticket:** PIX-9\n\n## 1\n", encoding="utf-8")
    assert autocommit.ticket(str(p)) == "PIX-9"
    assert autocommit.message("T2", "tag counts", str(p)) == "PIX-9 T2: tag counts"
    p.write_text("# P\n", encoding="utf-8")
    assert autocommit.ticket(str(p)) is None
    assert autocommit.message("T2", "tag counts", str(p)) == "T2: tag counts"
    assert autocommit.message("T2", "tag counts", None) == "T2: tag counts"
    assert autocommit.ticket(str(tmp_path / "missing.md")) is None


def test_also_dot_slash_path_normalised(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "Tests/Fake.txt", "fake\n")
    r = commit(repo, "T1", "--also", "./Tests/Fake.txt", "--ruling", RULING)
    assert r.returncode == 0, r.stdout + r.stderr
    assert files_of(repo) == ["Tests/Fake.txt", "src/a.py"]


def test_ticket_only_from_header_block(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("# P\n\n## Section\n\n### T1 x\n**Ticket:** BODY-1\n", encoding="utf-8")
    assert autocommit.ticket(str(p)) is None
    assert autocommit.message("T1", "x", str(p)) == "T1: x"


def test_also_directory_with_untracked_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "fixtures/noise/one.txt", "1\n")
    write(repo, "fixtures/noise/sub/two.txt", "2\n")
    r = commit(repo, "T1", "--also", "fixtures/noise", "--ruling", RULING, "--ledger", "led.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unchanged" not in r.stderr
    assert files_of(repo) == ["fixtures/noise/one.txt", "fixtures/noise/sub/two.txt", "src/a.py"]


def test_also_directory_trailing_slash(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "fixtures/noise/one.txt", "1\n")
    r = commit(repo, "T1", "--also", "fixtures/noise/", "--ruling", RULING, "--ledger", "led.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fixtures/noise/one.txt" in files_of(repo)
    assert "also commits fixtures/noise/ - " in (repo / "led.md").read_text(encoding="utf-8")
