"""commit_task import gate: files no import can name are skipped, optional dependencies warn (#471)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_pix_v2 import commit, repo_with, task  # noqa: E402
from test_run_scripts import SCRIPTS, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

OPT = '[project.optional-dependencies]\nnotebooks = ["marimo_absent_xyz>=0.9"]\n'
NEW_PY = pytest.mark.skipif(sys.version_info < (3, 11), reason="needs tomllib")


def test_dashed_folder_file_is_skipped(tmp_path):
    write(tmp_path, "agents/macos-import/fake_api.py", "import sys\nsys.exit(3)\n")
    notes = []
    assert commit_task.import_errors(["agents/macos-import/fake_api.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("skip", "agents/macos-import/fake_api.py", 0, "no module name")]


def test_non_identifier_stem_is_skipped(tmp_path):
    a = "docs/plans/2026-11-10-x.dash-120-migration.py"
    b = "notebooks/01_frame.py"
    write(tmp_path, a, 'raise RuntimeError("ran")\n')
    write(tmp_path, b, "import marimo_absent_xyz\n")
    notes = []
    assert commit_task.import_errors([a, b], [], root=tmp_path, notes=notes) == []
    assert notes == [("skip", a, 0, "no module name"), ("skip", b, 0, "no module name")]


def test_identifier_namespace_file_still_checked(tmp_path):
    write(tmp_path, "notebooks/frame.py", "import module_that_does_not_exist_xyz\n")
    notes = []
    errs = commit_task.import_errors(["notebooks/frame.py"], [], root=tmp_path, notes=notes)
    assert len(errs) == 1 and errs[0][:2] == ("notebooks/frame.py", 1)
    assert errs[0][2].startswith("ModuleNotFoundError")
    assert notes == []


@NEW_PY
def test_optional_dependency_is_a_warning(tmp_path):
    write(tmp_path, "pyproject.toml", OPT)
    write(tmp_path, "notebooks/frame.py", "import marimo_absent_xyz\n")
    notes = []
    assert commit_task.import_errors(["notebooks/frame.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("warn", "notebooks/frame.py", 1, "ModuleNotFoundError: No module named 'marimo_absent_xyz'")]


@NEW_PY
def test_main_dependency_still_blocks(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["marimo_absent_xyz"]\n' + OPT)
    write(tmp_path, "notebooks/frame.py", "import marimo_absent_xyz\n")
    notes = []
    errs = commit_task.import_errors(["notebooks/frame.py"], [], root=tmp_path, notes=notes)
    assert len(errs) == 1
    assert [n for n in notes if n[0] == "warn"] == []


@NEW_PY
def test_optional_deps_names(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["requests>=2"]\n'
          '[project.optional-dependencies]\nnotebooks = ["marimo>=0.9", "Plotly.Express"]\n'
          '[dependency-groups]\ndev = ["pytest", {include-group = "notebooks"}]\n'
          '[tool.uv]\ndev-dependencies = ["ruff"]\n')
    assert commit_task.optional_deps(tmp_path) == {"marimo", "plotly_express", "pytest", "ruff"}
    write(tmp_path, "pyproject.toml", "[project\n")
    assert commit_task.optional_deps(tmp_path) == set()
    (tmp_path / "pyproject.toml").unlink()
    assert commit_task.optional_deps(tmp_path) == set()


@NEW_PY
def test_commit_prints_skip_and_warning(tmp_path):
    repo = repo_with(tmp_path, task(1, ["tools-x/gen.py", "notebooks/frame.py"]))
    write(repo, "pyproject.toml", OPT)
    from test_run_scripts import git
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pyproject")
    write(repo, "tools-x/gen.py", "X = 1\n")
    write(repo, "notebooks/frame.py", "import marimo_absent_xyz\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    skip = "import check skipped (no module name): tools-x/gen.py"
    warn = ("import warning notebooks/frame.py:1 ModuleNotFoundError: No module named 'marimo_absent_xyz' "
            "(optional dependency not installed; not blocking)")
    assert r.stderr.count(skip) == 1
    assert r.stderr.count(warn) == 1
