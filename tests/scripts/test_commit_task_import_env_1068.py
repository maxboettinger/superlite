"""#1068: commit_task's import check: a missing declared dependency is an environment gap, a uv environment
that never starts the check is one too, and a standalone script's top-level code never runs."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_pix_v2 import commit, repo_with, task  # noqa: E402
from test_run_scripts import SCRIPTS, git, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import _pyrun  # noqa: E402
import commit_task  # noqa: E402

NEW_PY = pytest.mark.skipif(sys.version_info < (3, 11), reason="needs tomllib")
GAP = "; environment gap, not blocking)"
SKIP = "script: top-level code runs the program"


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def uv_cmd(root):
    return ["/opt/bin/uv", "run", "--frozen", "--project", str(root), "python"]


@NEW_PY
@pytest.mark.parametrize("pyproject,module", [
    ('[project]\ndependencies = ["fastapi_absent_xyz>=0.100"]\n', "fastapi_absent_xyz"),
    ('[project]\ndependencies = ["Pydantic-Settings-Absent-Xyz[dotenv]>=2"]\n', "pydantic_settings_absent_xyz"),
    ('[tool.poetry.dependencies]\npython = "^3.11"\ntyper_absent_xyz = "^0.9"\n', "typer_absent_xyz"),
])
def test_missing_declared_dependency_is_an_environment_gap(tmp_path, pyproject, module):
    write(tmp_path, "pyproject.toml", pyproject)
    write(tmp_path, "app/api.py", f"import os\nimport {module}\n")
    notes = []
    assert commit_task.import_errors(["app/api.py"], [], root=tmp_path, notes=notes) == []
    assert len(notes) == 1
    kind, f, line, msg = notes[0]
    assert (kind, f, line) == ("env", "app/api.py", 2)
    assert msg.startswith(f"ModuleNotFoundError: No module named '{module}' (declared dependency not installed under ")
    assert msg.endswith(GAP)


@NEW_PY
def test_undeclared_missing_module_still_blocks(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["fastapi_absent_xyz"]\n')
    write(tmp_path, "app/api.py", "import fastapi_absent_xyz_typo\n")
    notes = []
    errs = commit_task.import_errors(["app/api.py"], [], root=tmp_path, notes=notes)
    assert errs == [("app/api.py", 1, "ModuleNotFoundError: No module named 'fastapi_absent_xyz_typo'")]
    assert notes == []


@NEW_PY
def test_missing_submodule_of_a_declared_package_still_blocks(tmp_path):
    write(tmp_path, "pyproject.toml", '[project]\ndependencies = ["libx"]\n')
    write(tmp_path, "libx/__init__.py", "")
    write(tmp_path, "app/api.py", "import libx.nothere\n")
    notes = []
    errs = commit_task.import_errors(["app/api.py"], [], root=tmp_path, notes=notes)
    assert len(errs) == 1 and errs[0][:2] == ("app/api.py", 1)
    assert errs[0][2].startswith("ModuleNotFoundError: No module named 'libx.nothere'")
    assert notes == []


SCRIPT_SRC = {
    "argv": "import sys\nN = int(sys.argv[1])\n",
    "from_argv": "from sys import argv\nN = argv[1]\n",
    "argparse": "import argparse\nparser = argparse.ArgumentParser()\nargs = parser.parse_args()\n",
    "known_args": "import argparse\nargs, rest = argparse.ArgumentParser().parse_known_args()\n",
    "sys_exit": "import sys\ndef main():\n    return 0\nsys.exit(main())\n",
    "exit_builtin": "print('hi')\nexit(0)\n",
    "raise": "def main():\n    return 0\nraise SystemExit(main())\n",
    "nested": "import sys\ntry:\n    if len(sys.argv) > 1:\n        pass\nexcept Exception:\n    pass\n",
    "class_body": "import sys\nclass Cfg:\n    ARGS = sys.argv[1:]\n",
    "else_of_main_guard": "import sys\nif __name__ == '__main__':\n    pass\nelse:\n    sys.exit(2)\n",
}
MODULE_SRC = {
    "guarded": "import sys\ndef main():\n    return sys.argv[1:]\nif __name__ == '__main__':\n    sys.exit(main())\n",
    "reversed_guard": "import sys\nif '__main__' == __name__:\n    N = int(sys.argv[1])\n",
    "function": "import argparse\ndef cli(argv=None):\n    return argparse.ArgumentParser().parse_args(argv)\n",
    "async_function": "import sys\nasync def run():\n    sys.exit(1)\n",
    "method": "import sys\nclass C:\n    def run(self):\n        sys.exit(1)\n",
    "lambda": "import sys\nARGS = lambda: sys.argv\n",
    "other_attr": "import os\nHOME = os.environ.get('HOME')\n",
}


@pytest.mark.parametrize("name", sorted(SCRIPT_SRC))
def test_runs_on_import_finds_script_top_level_code(tmp_path, name):
    write(tmp_path, "scripts/s.py", SCRIPT_SRC[name])
    assert commit_task.runs_on_import(tmp_path / "scripts" / "s.py") is True


@pytest.mark.parametrize("name", sorted(MODULE_SRC))
def test_runs_on_import_leaves_guarded_code_alone(tmp_path, name):
    write(tmp_path, "scripts/m.py", MODULE_SRC[name])
    assert commit_task.runs_on_import(tmp_path / "scripts" / "m.py") is False


def test_runs_on_import_is_false_for_unparsable_or_missing_files(tmp_path):
    write(tmp_path, "bad.py", "def (:\n")
    assert commit_task.runs_on_import(tmp_path / "bad.py") is False
    assert commit_task.runs_on_import(tmp_path / "gone.py") is False


def test_script_is_never_imported(tmp_path):
    write(tmp_path, "scripts/bump.py", 'from pathlib import Path\nPath(__file__).with_name("ran.txt").write_text("x")\n'
          "import sys\nN = int(sys.argv[1])\n")
    write(tmp_path, "scripts/helper.py", "import sys\ndef args():\n    return sys.argv[1:]\n")
    notes = []
    assert commit_task.import_errors(["scripts/bump.py", "scripts/helper.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("skip", "scripts/bump.py", 0, SKIP)]
    assert not (tmp_path / "scripts" / "ran.txt").exists()


def test_unnamed_script_keeps_the_no_module_name_note(tmp_path):
    write(tmp_path, "tools-x/run.py", "import sys\nsys.exit(int(sys.argv[1]))\n")
    notes = []
    assert commit_task.import_errors(["tools-x/run.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("skip", "tools-x/run.py", 0, "no module name")]


def test_script_inside_a_package_is_skipped(tmp_path):
    write(tmp_path, "tools-x/pkg/__init__.py", "")
    write(tmp_path, "tools-x/pkg/cli.py", "import sys\nN = int(sys.argv[1])\n")
    notes = []
    assert commit_task.import_errors(["tools-x/pkg/cli.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("skip", "tools-x/pkg/cli.py", 0, SKIP)]


def test_uv_command_runs_the_check(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(_pyrun, "project_env", lambda root: (uv_cmd(root), ""))

    def fake_run(cmd, *a, **k):
        seen["cmd"], seen["env"] = cmd, k.get("env") or {}
        return subprocess.CompletedProcess(cmd, 0, "@import-check app/a.py\n[]\n", "")
    monkeypatch.setattr(commit_task.subprocess, "run", fake_run)
    assert commit_task.import_errors(["app/a.py"], ["src"], root=tmp_path) == []
    assert seen["cmd"][:9] == [*uv_cmd(tmp_path), "-I", "-c", commit_task.IMPORT_DRIVER]
    assert seen["cmd"][9:] == [str(tmp_path), json.dumps(["src"]), "app/a.py"]
    assert json.loads(seen["env"]["SUPERLITE_IMPORT_SCRIPTS"]) == []


def test_uv_environment_that_never_starts_is_a_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(_pyrun, "project_env", lambda root: (uv_cmd(root), ""))

    def slow(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd, k.get("timeout"), output="", stderr="Resolved 40 packages")
    monkeypatch.setattr(commit_task.subprocess, "run", slow)
    monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", "7")
    notes = []
    assert commit_task.import_errors(["app/a.py", "app/b.py"], [], root=tmp_path, notes=notes) == []
    assert [n[:3] for n in notes] == [("env", "app/a.py", 0), ("env", "app/b.py", 0)]
    assert notes[0][3] == (f"import check not run under {' '.join(uv_cmd(tmp_path))}: "
                           "the environment did not start in 7 s (environment gap, not blocking)")


def test_uv_environment_that_fails_to_build_is_a_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(_pyrun, "project_env", lambda root: (uv_cmd(root), ""))
    monkeypatch.setattr(commit_task.subprocess, "run", lambda cmd, *a, **k: subprocess.CompletedProcess(
        cmd, 2, "", "error: Failed to fetch: `https://pypi.org/simple/fastapi/`\n"))
    notes = []
    assert commit_task.import_errors(["app/a.py"], [], root=tmp_path, notes=notes) == []
    assert notes == [("env", "app/a.py", 0, f"import check not run under {' '.join(uv_cmd(tmp_path))}: "
                      "error: Failed to fetch: `https://pypi.org/simple/fastapi/` (environment gap, not blocking)")]


def test_uv_check_that_started_and_blocked_still_names_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(_pyrun, "project_env", lambda root: (uv_cmd(root), ""))

    def slow(cmd, *a, **k):
        raise subprocess.TimeoutExpired(cmd, 7, output="@import-check app/a.py\n@import-check app/b.py\n", stderr="")
    monkeypatch.setattr(commit_task.subprocess, "run", slow)
    monkeypatch.setenv("SUPERLITE_IMPORT_TIMEOUT", "7")
    notes = []
    errs = commit_task.import_errors(["app/a.py", "app/b.py"], [], root=tmp_path, notes=notes)
    assert [e[:2] for e in errs] == [("app/b.py", 0)]
    assert errs[0][2].startswith("TimeoutExpired: import did not finish in 7 s")
    assert notes == []


def test_interpreter_crash_without_uv_still_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(_pyrun, "project_env", lambda root: (["/x/venv/bin/python"], ""))
    monkeypatch.setattr(commit_task.subprocess, "run", lambda cmd, *a, **k: subprocess.CompletedProcess(cmd, 1, "", "boom"))
    notes = []
    errs = commit_task.import_errors(["app/a.py"], [], root=tmp_path, notes=notes)
    assert errs == [("app/a.py", 0, "import check crashed under /x/venv/bin/python: boom")]
    assert notes == []


@NEW_PY
def test_commit_goes_through_an_environment_gap_and_skips_a_script(tmp_path):
    repo = repo_with(tmp_path, task(1, ["app/api.py", "scripts/bump.py"]))
    write(repo, "pyproject.toml", '[project]\ndependencies = ["fastapi_absent_xyz"]\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pyproject")
    write(repo, "app/api.py", "import fastapi_absent_xyz\n")
    write(repo, "scripts/bump.py", "import sys\nN = int(sys.argv[1])\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.count(f"import check skipped ({SKIP}): scripts/bump.py") == 1
    head = ("import warning app/api.py:1 ModuleNotFoundError: No module named 'fastapi_absent_xyz' "
            "(declared dependency not installed under ")
    warn = [ln for ln in r.stderr.splitlines() if ln.startswith(head)]
    assert len(warn) == 1 and warn[0].endswith(GAP)
    log = repo / ".superlite" / "incidents.jsonl"
    assert "fastapi_absent_xyz" not in (log.read_text(encoding="utf-8") if log.exists() else "")


WHERE_LIB = "packages/lib/src"
FAKE_UV = r'''
import os
import sys

args = sys.argv[1:]
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "uv-args.txt"), "w") as f:
    f.write("\n".join(args))
i = args.index("python")
os.execv(sys.executable, [sys.executable, *args[i + 1:]])
'''


def editable_main(tmp_path):
    """A main checkout whose real .venv holds an editable-install .pth naming main's packages/lib/src, and a worktree nested in it."""
    main = tmp_path.resolve() / "main"
    write(main, f"{WHERE_LIB}/where1140/__init__.py", "WHERE = 'main'\n")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(main / ".venv")], check=True, capture_output=True)
    site = next((main / ".venv" / "lib").glob("python3*/site-packages"))
    (site / "where1140.pth").write_text(str(main / WHERE_LIB) + "\n")
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    wt = main / ".claude" / "worktrees" / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    write(wt, f"{WHERE_LIB}/where1140/__init__.py", "WHERE = 'tree'\n")
    write(wt, f"{WHERE_LIB}/where1140/only_tree.py", "from where1140 import WHERE\n\nassert WHERE == 'tree', WHERE\n")
    return main, wt


def fake_uv(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "fake_uv.py").write_text(FAKE_UV)
    uv = bindir / "uv"
    uv.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bindir / "fake_uv.py"}" "$@"\n')
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return bindir / "uv-args.txt"


@pytest.mark.skipif(os.name == "nt", reason="posix sh script and venv layout")
def test_import_check_in_a_nested_worktree_imports_the_worktree_code(tmp_path, monkeypatch):
    main, wt = editable_main(tmp_path)
    write(wt, "uv.lock", "")
    write(wt, "pyproject.toml", "[project]\nname = 'where1140'\n")
    args = fake_uv(tmp_path, monkeypatch)
    notes = []
    errs = commit_task.import_errors([f"{WHERE_LIB}/where1140/only_tree.py"], [WHERE_LIB], root=wt, notes=notes)
    assert errs == []
    assert notes == [("venv", "", 0, f"{main / '.venv'} is the main checkout's environment, outside {wt}; "
                      f"running the import check in {wt}'s own environment: uv run --frozen --project {wt} (#1140)")]
    assert args.read_text().splitlines()[:5] == ["run", "--frozen", "--project", str(wt), "python"]


@pytest.mark.skipif(os.name == "nt", reason="posix venv layout")
def test_import_check_without_uv_lock_names_the_main_env(tmp_path, monkeypatch):
    main, wt = editable_main(tmp_path)
    notes = []
    errs = commit_task.import_errors([f"{WHERE_LIB}/where1140/only_tree.py"], [WHERE_LIB], root=wt, notes=notes)
    assert [e[:2] for e in errs] == [(f"{WHERE_LIB}/where1140/only_tree.py", 0)]
    assert notes[0] == ("venv", "", 0, f"{main / '.venv'} is the main checkout's environment, outside {wt}, and {wt} has no uv.lock "
                        f"for an environment of its own; the import check may import that folder's package, not {wt}'s (#1140)")


@pytest.mark.skipif(os.name == "nt", reason="posix symlink")
def test_commit_in_a_linked_worktree_prints_the_venv_note(tmp_path):
    repo = repo_with(tmp_path, task(1, ["app/a.py"]))
    py = repo / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.symlink_to(sys.executable)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    write(wt, "app/a.py", "X = 1\n")
    r = commit(wt, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    head = f"import check: {repo.resolve() / '.venv'} is the main checkout's environment, outside {wt.resolve()}, and {wt.resolve()} has no uv.lock"
    assert sum(ln.startswith(head) for ln in r.stderr.splitlines()) == 1, r.stderr
