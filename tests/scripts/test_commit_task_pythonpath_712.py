"""#712: the import check names the pythonpath fix and skips fixture scripts."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_pix_v2 import commit, repo_with, task  # noqa: E402
from test_run_scripts import SCRIPTS, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

FIX = 'add "pythonpath": ["tools"] to .superlite/test-cmd.json'
ERR = "ModuleNotFoundError: No module named 'pkg'"


def pkg(root):
    write(root, "tools/pkg/__init__.py", "")
    write(root, "tools/pkg/b.py", "Y = 1\n")
    write(root, "tools/pkg/a.py", "from pkg import b\nX = b.Y\n")


def test_import_error_names_the_fix(tmp_path):
    pkg(tmp_path)
    assert commit_task.import_errors(["tools/pkg/a.py"], [], root=tmp_path) == [("tools/pkg/a.py", 1, f"{ERR}; {FIX}")]


def test_configured_root_imports(tmp_path):
    pkg(tmp_path)
    assert commit_task.import_errors(["tools/pkg/a.py"], ["tools"], root=tmp_path) == []


def test_module_nowhere_in_the_repo_has_no_fix(tmp_path):
    write(tmp_path, "tools/x.py", "import module_that_does_not_exist_xyz\n")
    assert commit_task.import_errors(["tools/x.py"], [], root=tmp_path) == [
        ("tools/x.py", 1, "ModuleNotFoundError: No module named 'module_that_does_not_exist_xyz'")]


def test_fixture_files_are_no_modules():
    assert commit_task.is_fixture("tests/fixtures/opens_a_file.py")
    assert not commit_task.is_module("tests/fixtures/opens_a_file.py")
    assert not commit_task.is_module("fixtures/x.py")
    assert not commit_task.is_fixture("tools/fixtures_util.py")
    assert commit_task.is_module("tools/fixtures_util.py")
    assert commit_task.is_module("tools/pkg/a.py")


def test_import_and_failed_lines_name_the_fix(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tools/pkg/__init__.py", "tools/pkg/a.py", "tools/pkg/b.py"]))
    pkg(repo)
    r = commit(repo, "T1")
    assert r.returncode != 0
    assert f"import tools/pkg/a.py:1 {ERR}; {FIX}" in r.stdout
    assert FIX in r.stdout.split("T1 FAILED: ", 1)[1]


def test_fixture_script_does_not_block(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tests/fixtures/opens_a_file.py", "tools/ok.py"]))
    write(repo, "tests/fixtures/opens_a_file.py", "open('data/missing.txt').read()\n")
    write(repo, "tools/ok.py", "X = 1\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.count("import check skipped (fixture): tests/fixtures/opens_a_file.py") == 1
