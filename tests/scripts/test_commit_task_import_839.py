"""#839: the import check skips __main__.py and reports a blocking import as a timeout, not a crash."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_pix_v2 import repo_with, task  # noqa: E402
from test_run_scripts import SCRIPTS, commit, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

CLI = "import argparse\n\n\ndef main():\n    argparse.ArgumentParser().parse_args()\n    return 0\n"
MAIN = "import sys\n\nfrom tool.cli import main\n\nsys.exit(main())\n"
BLOCK = "import time\n\ntime.sleep(60)\n"
FAST = {"SUPERLITE_IMPORT_TIMEOUT": "2"}
TIMEOUT = 'TimeoutExpired: import did not finish in 2 s (top-level code that blocks: move it under if __name__ == "__main__":)'


def test_main_files_are_no_modules():
    assert not commit_task.is_module("tool/__main__.py")
    assert not commit_task.is_module("src/pkg/__main__.py")
    assert not commit_task.is_module("__main__.py")
    assert commit_task.is_module("tool/cli.py")
    assert commit_task.is_module("tool/main.py")


def test_package_with_unguarded_main_commits(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tool/__init__.py", "tool/cli.py", "tool/__main__.py"]))
    write(repo, "tool/__init__.py", "")
    write(repo, "tool/cli.py", CLI)
    write(repo, "tool/__main__.py", MAIN)
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.count("import check skipped (__main__ runs the program): tool/__main__.py") == 1
    assert "SystemExit" not in r.stdout + r.stderr


def test_main_with_a_syntax_error_still_blocks(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tool/__init__.py", "tool/__main__.py"]))
    write(repo, "tool/__init__.py", "")
    write(repo, "tool/__main__.py", "def main(:\n")
    r = commit(repo, "T1")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "syntax tool/__main__.py:1" in r.stdout


def test_import_timeout_reads_the_env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_IMPORT_TIMEOUT", raising=False)
    assert commit_task.import_timeout() == 120
    for bad in ("", "abc", "0", "-5"):
        monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", bad)
        assert commit_task.import_timeout() == 120
    monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", "2.5")
    assert commit_task.import_timeout() == 2.5


def test_blocking_import_names_the_file_that_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", "3")
    write(tmp_path, "ok.py", "X = 1\n")
    write(tmp_path, "slow.py", BLOCK)
    write(tmp_path, "later.py", "Y = 2\n")
    errs = commit_task.import_errors(["ok.py", "slow.py", "later.py"], [], root=tmp_path)
    assert errs == [("slow.py", 0, TIMEOUT.replace("in 2 s", "in 3 s"))]


def test_blocking_import_fails_like_an_import_error(tmp_path):
    (tmp_path / "slow").mkdir()
    (tmp_path / "broken").mkdir()
    slow = repo_with(tmp_path / "slow", task(1, ["tools/slow.py"]))
    write(slow, "tools/slow.py", BLOCK)
    broken = repo_with(tmp_path / "broken", task(1, ["tools/bad.py"]))
    write(broken, "tools/bad.py", "import module_that_does_not_exist_xyz\n")
    want = commit(broken, "T1").returncode
    r = commit(slow, "T1", env=FAST)
    assert want == 1
    assert r.returncode == want, r.stdout + r.stderr
    assert f"import tools/slow.py:0 {TIMEOUT}" in r.stdout
    assert "T1 FAILED: import tools/slow.py:0 TimeoutExpired" in r.stdout
    assert "Traceback" not in r.stderr


def test_fixture_main_prints_only_the_fixture_note(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tests/fixtures/__main__.py"]))
    write(repo, "tests/fixtures/__main__.py", MAIN)
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "import check skipped (fixture): tests/fixtures/__main__.py" in r.stderr
    assert "__main__ runs the program" not in r.stderr


def test_import_timeout_rejects_inf_and_nan_and_the_marker_has_one_source(monkeypatch):
    for bad in ("inf", "nan", "1e999"):
        monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", bad)
        assert commit_task.import_timeout() == commit_task.IMPORT_TIMEOUT == 120
    assert commit_task.IMPORT_MARK == "@import-check "
    assert commit_task.IMPORT_MARK in commit_task.IMPORT_DRIVER
    assert "@IMPORT_MARK@" not in commit_task.IMPORT_DRIVER
