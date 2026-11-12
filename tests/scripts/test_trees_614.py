"""trees.clean_idle and trees.sweep_scratch_builds (#614)."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import trees  # noqa: E402


def _repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    for a in (["init", "-q"], ["config", "user.email", "a@b"], ["config", "user.name", "n"],
              ["commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)
    return r


def test_clean_idle_drops_idle_trees_and_keeps_busy(tmp_path):
    r = _repo(tmp_path)
    for k in ("T1", "T3", "worker-W2"):
        trees.prepare(r, k, [])
    (r / trees.TREES / f"T3.busy.{os.getpid()}").write_text("")
    assert trees.clean_idle(r) == ["T1", "worker-W2"]
    assert trees.tree_path(r, "T3").is_dir() and not trees.tree_path(r, "T1").exists()


def test_clean_idle_without_trees_folder(tmp_path):
    assert trees.clean_idle(tmp_path) == []


def test_clean_idle_drops_a_tree_of_a_dead_pid_marker(tmp_path):
    r = _repo(tmp_path)
    trees.prepare(r, "T1", [])
    (r / trees.TREES / "T1.busy.999999999").write_text("")
    assert trees.clean_idle(r) == ["T1"]


def _build(d, size=3):
    (d / "Build").mkdir(parents=True)
    (d / "Build" / "x.o").write_bytes(b"x" * size)
    (d / "Logs").mkdir()


def test_sweep_removes_build_folder_keeps_scratchpad(tmp_path):
    H = tmp_path / "H"
    sp = H / "-w-b1" / "s1" / "scratchpad"
    _build(sp / "dd")
    assert trees.sweep_scratch_builds("/w/b1", home=H) == (1, 3)
    assert not (sp / "dd").exists() and sp.is_dir()


def test_sweep_nothing_to_remove(tmp_path):
    H = tmp_path / "H"
    sp = H / "-w-b1" / "s1" / "scratchpad"
    sp.mkdir(parents=True)
    (sp / "notes.md").write_text("n")
    assert trees.sweep_scratch_builds("/w/b1", home=H) == (0, 0)
    assert (sp / "notes.md").exists()


def test_scratch_sweep_never_leaves_its_slug(tmp_path):
    H = tmp_path / "H"
    _build(H / "-w-b2" / "s1" / "scratchpad" / "dd")
    assert trees.sweep_scratch_builds("/w/b1", home=H) == (0, 0)
    assert (H / "-w-b2" / "s1" / "scratchpad" / "dd").exists()


def test_scratch_sweep_keeps_a_symlinked_build_folder_target(tmp_path):
    H = tmp_path / "H"
    target = tmp_path / "elsewhere"
    _build(target)
    sp = H / "-w-b1" / "s1" / "scratchpad"
    sp.mkdir(parents=True)
    (sp / "dd").symlink_to(target)
    assert trees.sweep_scratch_builds("/w/b1", home=H) == (0, 0)
    assert (target / "Build" / "x.o").exists()


def test_scratch_home_default(monkeypatch):
    monkeypatch.delenv("SUPERLITE_SCRATCH_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_TMPDIR", raising=False)
    assert trees.scratch_home() == Path(f"/tmp/claude-{os.getuid()}")
    monkeypatch.setenv("CLAUDE_CODE_TMPDIR", "/x")
    assert trees.scratch_home() == Path(f"/x/claude-{os.getuid()}")


def test_scratch_sweep_resolved_path_slug(tmp_path):
    real = tmp_path / "real" / "wt"
    real.mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    H = tmp_path / "H"
    _build(H / trees._slug(real.resolve()) / "s1" / "scratchpad" / "dd")
    assert trees.sweep_scratch_builds(tmp_path / "link" / "wt", home=H) == (1, 3)


def test_module_cache_alone_counts(tmp_path):
    H = tmp_path / "H"
    mc = H / "-w-b1" / "s1" / "scratchpad" / "mc" / "ModuleCache.noindex"
    mc.mkdir(parents=True)
    (mc / "a.pcm").write_bytes(b"abcd")
    assert trees.sweep_scratch_builds("/w/b1", home=H) == (1, 4)
    assert not mc.parent.exists()
