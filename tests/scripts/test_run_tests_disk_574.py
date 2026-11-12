"""run_tests: tree build path, busy reap, disk gate, ENOSPC (GitHub #574)."""
import errno
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS
from test_run_tests_plan_fallback import OUT, setup

sys.path.insert(0, str(SCRIPTS))
import run_tests as rt  # noqa: E402
import trees  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
T = "/r/.superlite/trees/T1"
DD = "/r/.superlite/trees/T1/.build/DerivedData"


@pytest.mark.parametrize("cmd,want", [
    ("xcodebuild test -scheme App", f"xcodebuild -derivedDataPath {DD} test -scheme App"),
    ("set -o pipefail && xcodebuild test -scheme App | xcpretty", f"set -o pipefail && xcodebuild -derivedDataPath {DD} test -scheme App | xcpretty"),
    ("/usr/bin/xcodebuild test -xctestrun x.xctestrun", f"/usr/bin/xcodebuild -derivedDataPath {DD} test -xctestrun x.xctestrun"),
    ("xcodebuild -list; xcodebuild test -scheme A", f"xcodebuild -list; xcodebuild -derivedDataPath {DD} test -scheme A"),
    ("xcodebuild -list", "xcodebuild -list"),
    ("xcodebuild test -scheme App -derivedDataPath dd", "xcodebuild test -scheme App -derivedDataPath dd"),
    ("swift test", "swift test"),
    ("xcodebuildx test -scheme A", "xcodebuildx test -scheme A"),
    ("xcodebuild -version && xcodebuild test -scheme A", f"xcodebuild -version && xcodebuild -derivedDataPath {DD} test -scheme A"),
    ("xcodebuild -showsdks", "xcodebuild -showsdks"),
    ("xcodebuild build -scheme A -derivedDataPath x; xcodebuild test -scheme A", f"xcodebuild build -scheme A -derivedDataPath x; xcodebuild -derivedDataPath {DD} test -scheme A"),
])
def test_with_derived_data(cmd, want):
    assert rt.with_derived_data(cmd, T) == want


def test_with_derived_data_quotes_a_tree_with_spaces():
    assert rt.with_derived_data("xcodebuild test -scheme A", "/r s/T1") == "xcodebuild -derivedDataPath '/r s/T1/.build/DerivedData' test -scheme A"


def fake_xcodebuild(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    x = b / "xcodebuild"
    x.write_text(f'#!/bin/sh\necho "$@" > "{tmp_path}/args.txt"\necho "{OUT}"\n', encoding="utf-8")
    x.chmod(0o755)
    return {"PATH": f"{b}{os.pathsep}{os.environ['PATH']}"}


def set_cmd(tmp_path, cmd):
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd}), encoding="utf-8")


def run_env(tmp_path, *args, env=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    return subprocess.run([sys.executable, str(RUN_TESTS), *map(str, args)], capture_output=True, text=True, cwd=tmp_path, env=e, timeout=120)


def test_tree_run_builds_in_the_trees_derived_data(tmp_path):
    plan = setup(tmp_path)
    set_cmd(tmp_path, "xcodebuild test -scheme App")
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env=fake_xcodebuild(tmp_path))
    assert cp.returncode == 0, cp.stdout + cp.stderr
    args = (tmp_path / "args.txt").read_text(encoding="utf-8").split()
    tree = (tmp_path / ".superlite" / "trees" / "T1").resolve()
    assert args[0] == "-derivedDataPath" and Path(args[1]).resolve() == tree / ".build" / "DerivedData"
    assert args[2:] == ["test", "-scheme", "App"]
    assert "(removed with the tree)" in cp.stderr


def test_root_run_leaves_xcodebuild_unchanged(tmp_path):
    setup(tmp_path)
    set_cmd(tmp_path, "xcodebuild test -scheme App")
    cp = run_env(tmp_path, "--full", env=fake_xcodebuild(tmp_path))
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (tmp_path / "args.txt").read_text(encoding="utf-8") == "test -scheme App\n"


def test_gate_refuses_below_the_floor(tmp_path):
    plan = setup(tmp_path)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "999999", "SUPERLITE_DISK_WARN_GB": "1999999"})
    assert cp.returncode == 2
    assert "run_tests: disk: " in cp.stderr and "below the 999999 GB floor" in cp.stderr
    data = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert data["error"].startswith("disk: ")
    assert not (tmp_path / ".superlite" / "trees" / "T1").exists()


def test_gate_warns_below_the_warn_level(tmp_path):
    plan = setup(tmp_path)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "999999"})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "run_tests: disk: WARNING: " in cp.stderr


def test_run_reaps_unneeded_trees_but_keeps_its_own(tmp_path):
    plan = setup(tmp_path)
    for k in ("T1", "T7", "worker-W3", "worker-W4"):
        trees.prepare(tmp_path, k, [])
    (tmp_path / ".superlite" / "progress.md").write_text("- commit T1 abcdef1234 t1\n- commit T7 abcdef1234 t7\n", encoding="utf-8")
    (tmp_path / ".superlite" / "fleet.json").write_text(json.dumps({"workers": {"W3": {"state": "stopped"}, "W4": {"state": "ready"}}}), encoding="utf-8")
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "run_tests: removed 2 tree(s) nothing needs: T7, worker-W3" in cp.stderr
    base = tmp_path / ".superlite" / "trees"
    assert (base / "T1").is_dir() and (base / "worker-W4").is_dir()
    assert not (base / "T7").exists() and not (base / "worker-W3").exists()


def test_enospc_is_a_clear_exit_without_traceback(tmp_path, monkeypatch, capsys):
    (tmp_path / ".superlite").mkdir()
    monkeypatch.chdir(tmp_path)

    def boom(a):
        raise OSError(errno.ENOSPC, "No space left on device", "/x/test-summary.json")

    def full(*_a, **_k):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(rt, "run", boom)
    monkeypatch.setattr(rt, "write_summary", full)
    assert rt.main(["--full"]) == 2
    err = capsys.readouterr().err
    assert "run_tests: disk full (ENOSPC): No space left on device: /x/test-summary.json; run sl trees clean and free space, then rerun" in err
    assert "Traceback" not in err


def test_tree_is_busy_from_prepare_to_the_end_of_the_run(tmp_path, monkeypatch):
    plan = setup(tmp_path)
    seen = {}
    real = trees.prepare

    def prepare(root, key, owns):
        seen["in_prepare"] = trees.is_busy(root, key)
        return real(root, key, owns)

    monkeypatch.setattr(trees, "prepare", prepare)
    monkeypatch.chdir(tmp_path)
    marks = tmp_path / "marks.txt"
    cmd = f"{sys.executable} -c \"import glob;open('{marks}','w').write(str(len(glob.glob('{tmp_path}/.superlite/trees/T1.busy.*'))));print('{OUT}')\""
    set_cmd(tmp_path, cmd)
    assert rt.main(["--full", "--task", "T1", "--plan", str(plan)]) == 0
    assert seen["in_prepare"] is True
    assert marks.read_text(encoding="utf-8") == "1"
    assert not trees.is_busy(tmp_path, "T1")


def orphan(tmp_path):
    home = tmp_path / "dd"
    folder = home / "App-abc"
    folder.mkdir(parents=True)
    (folder / "info.plist").write_bytes(plistlib.dumps({"WorkspacePath": str(tmp_path / ".superlite" / "trees" / "T9" / "App.xcodeproj")}))
    (folder / "x.bin").write_text("x" * 100, encoding="utf-8")
    return home, folder


def test_gate_sweeps_before_it_refuses(tmp_path):
    plan = setup(tmp_path)
    home, folder = orphan(tmp_path)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "999999", "SUPERLITE_DISK_WARN_GB": "1999999", "SUPERLITE_DERIVED_DATA_HOME": str(home)})
    assert cp.returncode == 2
    assert "below the 999999 GB floor" in cp.stderr
    assert not folder.exists()


def test_no_sweep_when_the_disk_is_fine(tmp_path):
    plan = setup(tmp_path)
    home, folder = orphan(tmp_path)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "0", "SUPERLITE_DERIVED_DATA_HOME": str(home)})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert folder.exists()


def test_tree_setup_builds_in_the_trees_derived_data(tmp_path):
    plan = setup(tmp_path)
    x = fake_xcodebuild(tmp_path)
    (tmp_path / "bin" / "xcodebuild").write_text(f'#!/bin/sh\necho "$@" >> "{tmp_path}/args.txt"\necho "{OUT}"\n', encoding="utf-8")
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": "xcodebuild test -scheme App", "test_file": "xcodebuild test -scheme App", "setup": "xcodebuild build-for-testing -scheme App"}), encoding="utf-8")
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env=x)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    lines = (tmp_path / "args.txt").read_text(encoding="utf-8").splitlines()
    tree = (tmp_path / ".superlite" / "trees" / "T1").resolve()
    assert lines[0].startswith("-derivedDataPath ") and lines[0].split()[1].endswith(".build/DerivedData")
    assert Path(lines[0].split()[1]).resolve() == tree / ".build" / "DerivedData"
    assert lines[0].split()[2] == "build-for-testing"
