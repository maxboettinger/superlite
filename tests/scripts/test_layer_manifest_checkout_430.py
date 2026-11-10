"""test_layers keeps the last green file manifest per checkout, so one worktree's stamp never reads stale from another's files (#430)."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
spec = importlib.util.spec_from_file_location("test_layers_430", SCRIPTS / "test_layers.py")
tl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tl)  # puts scripts/ on sys.path and imports layer_store
ls = tl.layer_store

FILES = ["hooks/x", "hooks/session-start", "skills/a/SKILL.md", "agents/a.md", "commands/a.md", "evals/c/prompt.md"]


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def cli(root, *args):
    """test_layers.py on ROOT with the default store (the git common dir's, shared by every worktree)."""
    env = {**os.environ, "SUPERLITE_TEST_LAYERS": ""}
    return subprocess.run([sys.executable, str(SCRIPTS / "test_layers.py"), *args, "--root", str(root)],
                          capture_output=True, text=True, env=env)


def unit_line(root):
    return next((l for l in cli(root, "check").stdout.splitlines() if l.startswith("unit ")), "")


@pytest.fixture
def s(tmp_path):
    return tmp_path / "store" / "test-layers.json"


@pytest.fixture
def dirs(tmp_path):
    out = []
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        out.append(str((tmp_path / name).resolve()))
    return out


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "a@b.c")
    git(root, "config", "user.name", "t")
    for f in FILES:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def test_manifest_kept_per_checkout(s, dirs):
    a, b = dirs
    ls.record_green(s, "unit", "h1", {"x.py": "1"}, checkout=a)
    ls.record_green(s, "unit", "h2", {"x.py": "2", "y.py": "1"}, checkout=b)
    assert ls.is_green(s, "unit", "h1") and ls.is_green(s, "unit", "h2")
    assert ls.changed_files(s, "unit", {"x.py": "1"}, checkout=a) == []
    assert ls.changed_files(s, "unit", {"x.py": "1"}, checkout=b) == ["x.py", "y.py"]
    assert ls.has_manifest(s, "unit", checkout=a) and ls.has_manifest(s, "unit", checkout=b)
    assert ls.has_manifest(s, "unit") is False
    assert ls.has_manifest(s, "unit", checkout=a + "-other") is False


def test_checkout_never_reads_the_shared_manifest(s, dirs):
    a, _ = dirs
    ls.record_green(s, "unit", "h1", {"x.py": "1"})
    assert ls.has_manifest(s, "unit") is True
    assert ls.has_manifest(s, "unit", checkout=a) is False
    assert ls.changed_files(s, "unit", {"x.py": "1"}, checkout=a) == ["x.py"]
    assert ls.changed_files(s, "unit", {"x.py": "1"}) == []


def test_record_drops_removed_checkouts_and_the_shared_manifest(s, dirs):
    a, b = dirs
    ls.record_green(s, "unit", "h0", {"x.py": "0"})
    ls.record_green(s, "unit", "h1", {"x.py": "1"}, checkout=a)
    shutil.rmtree(a)
    ls.record_green(s, "unit", "h2", {"x.py": "2"}, checkout=b)
    entry = json.loads(s.read_text())["layers"]["unit"]
    assert entry == {"green": ["h0", "h1", "h2"], "checkouts": {b: {"x.py": "2"}}}
    ls.record_green(s, "unit", "h3", {"x.py": "3"})
    entry = json.loads(s.read_text())["layers"]["unit"]
    assert entry["files"] == {"x.py": "3"} and entry["checkouts"] == {b: {"x.py": "2"}}


def test_malformed_checkouts_read_as_no_manifest(s, dirs):
    a, _ = dirs
    s.parent.mkdir(parents=True)
    for bad in ([a], {a: ["x.py"]}, {a: 3}):
        s.write_text(json.dumps({"version": 1, "layers": {"unit": {"green": ["h0"], "checkouts": bad}}}))
        assert ls.has_manifest(s, "unit", checkout=a) is False
        assert ls.changed_files(s, "unit", {"x.py": "1"}, checkout=a) == ["x.py"]
    ls.record_green(s, "unit", "h1", {"x.py": "1"}, checkout=a)
    assert ls.changed_files(s, "unit", {"x.py": "1"}, checkout=a) == []
    assert ls.is_green(s, "unit", "h0") and ls.is_green(s, "unit", "h1")


def test_write_stamp_keys_the_manifest_by_resolved_root(s, tmp_path):
    root = tmp_path / "r"
    (root / "sub").mkdir(parents=True)
    key = str(root.resolve())
    assert tl.checkout_key(root / "sub" / "..") == key
    tl.write_stamp(root / "sub" / "..", s, "unit", {"a.py": "1"})
    assert ls.changed_files(s, "unit", {"a.py": "1"}, checkout=key) == []
    assert tl.stale_detail(s, "unit", {"a.py": "2", "b.py": "1"}, key) == "a.py, b.py"
    assert tl.stale_detail(s, "unit", {"a.py": "2"}, str(tmp_path / "other")) == "no green stamp"


def test_worktree_detail_names_only_its_own_changes(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    (wt / "hooks" / "lead1").write_text("1\n")
    assert cli(wt, "run", "unit", "--command-override", "unit=true").returncode == 0
    (repo / "hooks" / "main1").write_text("1\n")
    assert cli(repo, "run", "unit", "--command-override", "unit=true").returncode == 0
    (wt / "hooks" / "lead2").write_text("1\n")
    assert unit_line(wt) == "unit stale: hooks/lead2"
    assert unit_line(repo) == ""
    (repo / "hooks" / "x").write_text("2\n")
    assert unit_line(repo) == "unit stale: hooks/x"
    fresh = tmp_path / "fresh"
    git(repo, "worktree", "add", "-q", str(fresh), "-b", "fresh")
    assert unit_line(fresh) == "unit stale: no green stamp"
    store = json.loads((repo / ".git" / "superlite" / "test-layers.json").read_text())
    assert sorted(store["layers"]["unit"]["checkouts"]) == sorted([str(repo.resolve()), str(wt.resolve())])
