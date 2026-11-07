"""commit_task import check: a file inside a package imports by its dotted name from the package base."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_plan_tools import SCRIPTS  # noqa: E402
from test_commit_pix_v2 import commit, repo_with, task  # noqa: E402
from test_run_scripts import write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

REPO = HERE.parent.parent


def test_real_probe_pack_imports():
    pack = REPO / "skills/subagent-driven-development/probes/pack"
    files = sorted(p.relative_to(REPO).as_posix() for p in pack.glob("*.py"))
    assert files
    assert commit_task.import_errors(files, [], root=REPO) == []


def test_package_under_dashed_folder(tmp_path):
    write(tmp_path, "d-x/probes/pack/__init__.py", "")
    write(tmp_path, "d-x/probes/pack/_common.py", "P = 1\n")
    write(tmp_path, "d-x/probes/pack/file.py", "from pack._common import P\n")
    assert commit_task.import_errors(["d-x/probes/pack/file.py"], [], root=tmp_path) == []


def test_relative_import_in_package(tmp_path):
    write(tmp_path, "d-x/lib/pkg/__init__.py", "")
    write(tmp_path, "d-x/lib/pkg/a.py", "X = 1\n")
    write(tmp_path, "d-x/lib/pkg/b.py", "from .a import X\n")
    assert commit_task.import_errors(["d-x/lib/pkg/b.py"], [], root=tmp_path) == []


def test_nested_package_base(tmp_path):
    write(tmp_path, "d-x/top/pkg/__init__.py", "")
    write(tmp_path, "d-x/top/pkg/sub/__init__.py", "")
    write(tmp_path, "d-x/top/pkg/sub/n.py", "N = 2\n")
    write(tmp_path, "d-x/top/pkg/sub/m.py", "from pkg.sub.n import N\n")
    assert commit_task.import_errors(["d-x/top/pkg/sub/m.py"], [], root=tmp_path) == []


def test_package_init_itself(tmp_path):
    write(tmp_path, "d-x/probes/pack/_common.py", "P = 1\n")
    write(tmp_path, "d-x/probes/pack/__init__.py", "from pack._common import P\n")
    assert commit_task.import_errors(["d-x/probes/pack/__init__.py"], [], root=tmp_path) == []


def test_broken_import_in_package_still_reported(tmp_path):
    write(tmp_path, "d-x/probes/pack/__init__.py", "")
    write(tmp_path, "d-x/probes/pack/_common.py", "P = 1\n")
    write(tmp_path, "d-x/probes/pack/bad.py", "from pack._common import Missing\n")
    errs = commit_task.import_errors(["d-x/probes/pack/bad.py"], [], root=tmp_path)
    assert len(errs) == 1
    assert errs[0][0] == "d-x/probes/pack/bad.py"
    assert errs[0][1] == 1
    assert errs[0][2].startswith("ImportError")


def test_plain_dashed_file_unchanged(tmp_path):
    write(tmp_path, "d-x/tool.py", "import helper\n")
    write(tmp_path, "d-x/helper.py", "H = 1\n")
    assert commit_task.import_errors(["d-x/tool.py"], [], root=tmp_path) == []


def test_dashed_package_name_falls_back(tmp_path):
    write(tmp_path, "d-x/my-pkg/__init__.py", "")
    write(tmp_path, "d-x/my-pkg/m.py", "import os\n")
    assert commit_task.import_errors(["d-x/my-pkg/m.py"], [], root=tmp_path) == []


def test_walk_stops_at_root(tmp_path):
    write(tmp_path, "__init__.py", "")
    write(tmp_path, "d-x/__init__.py", "")
    write(tmp_path, "d-x/m.py", "M = 1\n")
    assert commit_task.import_errors(["d-x/m.py"], [], root=tmp_path) == []


def test_commit_task_commits_probe_like_package(tmp_path):
    files = ["d-x/probes/pack/__init__.py", "d-x/probes/pack/_common.py", "d-x/probes/pack/file.py"]
    repo = repo_with(tmp_path, task(1, files))
    write(repo, files[0], "")
    write(repo, files[1], "P = 1\n")
    write(repo, files[2], "from pack._common import P\n")
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "No module named" not in r.stdout


def test_same_package_name_in_two_dashed_folders(tmp_path):
    for d in ("d-a", "d-b"):
        write(tmp_path, f"{d}/pack/__init__.py", "")
        write(tmp_path, f"{d}/pack/_common.py", "P = 1\n")
    write(tmp_path, "d-a/pack/file.py", "from pack._common import P\n")
    write(tmp_path, "d-b/pack/file.py", "from pack._common import P\nfrom pack import only_b\n")
    write(tmp_path, "d-b/pack/only_b.py", "B = 1\n")
    errs = commit_task.import_errors(["d-a/pack/file.py", "d-b/pack/file.py"], [], root=tmp_path)
    assert errs == []
    write(tmp_path, "d-b/pack/file.py", "from pack._common import Nope\n")
    errs = commit_task.import_errors(["d-a/pack/file.py", "d-b/pack/file.py"], [], root=tmp_path)
    assert [(e[0], e[1]) for e in errs] == [("d-b/pack/file.py", 1)]


def test_dashed_package_name_sees_base_siblings(tmp_path):
    write(tmp_path, "d-x/helper.py", "H = 1\n")
    write(tmp_path, "d-x/my-pkg/__init__.py", "")
    write(tmp_path, "d-x/my-pkg/m.py", "import helper\n")
    assert commit_task.import_errors(["d-x/my-pkg/m.py"], [], root=tmp_path) == []
