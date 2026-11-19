"""sl -C DIR / --root DIR runs the tool in DIR, so calls need no `cd <worktree> &&` (#811)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SL = ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl"
pytestmark = pytest.mark.skipif(os.name == "nt", reason="the fake interpreter is a POSIX shell script")


def _sl(tmp_path, *args, cwd=None):
    fake = tmp_path / "fakepy"
    fake.write_text('#!/bin/sh\nprintf "%s\\n" "$(pwd -P)" "$@"\n', encoding="utf-8")
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "SUPERLITE_SL"}
    env.update(SUPERLITE_PYTHON=str(fake), SUPERLITE_CACHE_DIR=str(tmp_path / "cache"))
    return subprocess.run([shutil.which("bash"), str(SL), *args], capture_output=True, text=True, env=env, cwd=cwd or tmp_path)


@pytest.mark.parametrize("opt", [["-C", "{d}"], ["--root", "{d}"], ["--root={d}"]])
def test_option_runs_the_tool_in_dir(tmp_path, opt):
    d = tmp_path / "wt"
    d.mkdir()
    r = _sl(tmp_path, *[o.format(d=d) for o in opt], "metrics", "--plan", ".superlite")
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[0] == os.path.realpath(d) and out[1].endswith("/metrics.py") and out[2:] == ["--plan", ".superlite"]


def test_repeated_c_is_relative(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    r = _sl(tmp_path, "-C", str(tmp_path / "a"), "-C", "b", "metrics")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[0] == os.path.realpath(tmp_path / "a" / "b")


def test_bad_dir_exits_2_and_runs_nothing(tmp_path):
    missing = tmp_path / "nope"
    r = _sl(tmp_path, "-C", str(missing), "metrics")
    assert r.returncode == 2 and r.stdout == ""
    assert f"sl: -C {missing}: not a directory" in r.stderr
    r = _sl(tmp_path, f"--root={missing}", "metrics")
    assert r.returncode == 2 and f"sl: --root {missing}: not a directory" in r.stderr


@pytest.mark.parametrize("args,msg", [(["-C"], "sl: -C needs a directory"), (["--root"], "sl: --root needs a directory"),
                                      (["--root=", "metrics"], "sl: --root needs a directory"), (["-C", "", "metrics"], "sl: -C needs a directory")])
def test_missing_dir_exits_2(tmp_path, args, msg):
    r = _sl(tmp_path, *args)
    assert r.returncode == 2 and r.stdout == "" and msg in r.stderr


def test_no_option_keeps_cwd(tmp_path):
    d = tmp_path / "here"
    d.mkdir()
    r = _sl(tmp_path, "metrics", "x", cwd=d)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == os.path.realpath(d) and r.stdout.splitlines()[2:] == ["x"]


def test_version_and_usage_after_c(tmp_path):
    r = _sl(tmp_path, "-C", str(tmp_path), "version")
    assert r.returncode == 0 and r.stdout.startswith("superlite ")
    r = _sl(tmp_path, "-C", str(tmp_path))
    assert r.returncode == 2 and "usage: sl [-C DIR | --root DIR] <tool> [args...]" in r.stderr
