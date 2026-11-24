"""#1145: pt_review (introspection, server runner) and probe_run's worker use a linked worktree's or task tree's own interpreter, not the main checkout's .venv: a uv project root syncs its own .venv once (uv sync --frozen --project <root>), #1140's rule."""
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
PROBE_RUN = SCRIPTS.parent / "probes" / "probe_run.py"
sys.path.insert(0, str(SCRIPTS))
import _pyrun  # noqa: E402
import pt_review  # noqa: E402

UV = "/opt/bin/uv"
LIB = "packages/lib/src"
posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX venv layout and a shell-script uv")


class Stop(Exception):
    pass


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.setattr(_pyrun, "_SYNCED", {})
    monkeypatch.setattr(_pyrun, "_NOTED", set())


@pytest.fixture
def uv_on_path(monkeypatch):
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: UV if name == "uv" else None)


def touch(base, rel, text=""):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def linked(main, wt, name="wt"):
    """wt laid out as git writes a linked worktree of main (no git run)."""
    gitdir = main / ".git" / "worktrees" / name
    gitdir.mkdir(parents=True, exist_ok=True)
    (gitdir / "commondir").write_text("../..\n")
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    return wt


def checkout(tmp_path, lock=True):
    """A main checkout with a .venv interpreter and a uv worktree nested in it without one."""
    main = tmp_path.resolve() / "main"
    touch(main, ".venv/bin/python")
    wt = linked(main, main / ".claude" / "worktrees" / "wt")
    touch(wt, "pyproject.toml", "[project]\nname = 'x'\n")
    if lock:
        touch(wt, "uv.lock")
    return main, wt


def base(main, wt):
    return f"{main / '.venv'} is the main checkout's environment, outside {wt}"


class FakeSync:
    """Stands in for _pyrun.run_tree: records each call; a green sync writes <project>/.venv/bin/python."""

    def __init__(self, returncode=0, stderr="", exc=None):
        self.calls, self.returncode, self.stderr, self.exc = [], returncode, stderr, exc

    def __call__(self, cmd, timeout=None, **kw):
        self.calls.append((cmd, timeout, kw))
        if self.exc:
            raise self.exc
        if self.returncode == 0:
            touch(Path(cmd[-1]), ".venv/bin/python")
        return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)


def test_uv_worktree_syncs_its_own_venv_once(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    sync = FakeSync()
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    own = str(wt / ".venv" / "bin" / "python")
    assert _pyrun.own_python(wt) == (own, f"{base(main, wt)}; synced {wt}'s own environment once: uv sync --frozen --project {wt} (#1145)")
    assert [c[0] for c in sync.calls] == [[UV, "sync", "--frozen", "--project", str(wt)]]
    assert _pyrun.own_python(wt) == (own, "")
    assert len(sync.calls) == 1


def test_sync_runs_in_the_root_without_virtual_env_or_project_environment(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    monkeypatch.setenv("VIRTUAL_ENV", str(main / ".venv"))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(tmp_path / "elsewhere"))
    sync = FakeSync()
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    _pyrun.own_python(wt)
    (cmd, timeout, kw), = sync.calls
    assert timeout == _pyrun.SYNC_TIMEOUT == 300
    assert kw["cwd"] == str(wt)
    assert "VIRTUAL_ENV" not in kw["env"] and "UV_PROJECT_ENVIRONMENT" not in kw["env"]
    assert kw["env"]["PATH"] == os.environ["PATH"]


def test_failed_sync_keeps_main_env_with_note_and_is_not_retried(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    sync = FakeSync(returncode=2, stderr="Resolved 3 packages\nerror: The lockfile at `uv.lock` needs to be updated\n")
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    want = (str(main / ".venv" / "bin" / "python"),
            f"{base(main, wt)}; uv sync --frozen --project {wt} failed: error: The lockfile at `uv.lock` needs to be updated; "
            f"this check may import that folder's package, not {wt}'s (#1145)")
    assert _pyrun.own_python(wt) == want
    assert _pyrun.own_python(wt) == want
    assert len(sync.calls) == 1


def test_sync_timeout_keeps_main_env(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    monkeypatch.setattr(_pyrun, "run_tree", FakeSync(exc=subprocess.TimeoutExpired(["uv"], 300)))
    py, note = _pyrun.own_python(wt)
    assert py == str(main / ".venv" / "bin" / "python")
    assert f"; uv sync --frozen --project {wt} failed: timed out after 300 s; this check may import" in note


def test_sync_without_an_interpreter_keeps_main_env(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    monkeypatch.setattr(_pyrun, "run_tree", lambda cmd, timeout=None, **kw: subprocess.CompletedProcess(cmd, 0, "", ""))
    py, note = _pyrun.own_python(wt)
    assert py == str(main / ".venv" / "bin" / "python")
    assert f"failed: {wt / '.venv'} holds no interpreter after the sync; this check may import" in note


def test_worktree_without_lock_keeps_main_env_with_note(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path, lock=False)
    sync = FakeSync()
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    assert _pyrun.own_python(wt) == (
        str(main / ".venv" / "bin" / "python"),
        f"{base(main, wt)}, and {wt} has no uv.lock for an environment of its own; this check may import that folder's package, not {wt}'s (#1145)")
    assert sync.calls == []


def test_uv_missing_keeps_main_env_with_note(tmp_path, monkeypatch):
    main, wt = checkout(tmp_path)
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: None)
    sync = FakeSync()
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    assert _pyrun.own_python(wt)[1] == (
        f"{base(main, wt)}, and uv is not on PATH for {wt}'s own environment; this check may import that folder's package, not {wt}'s (#1145)")
    assert sync.calls == []


def test_own_venv_and_main_checkout_never_sync(tmp_path, monkeypatch, uv_on_path):
    main, wt = checkout(tmp_path)
    touch(main, "uv.lock")
    touch(main, "pyproject.toml")
    sync = FakeSync()
    monkeypatch.setattr(_pyrun, "run_tree", sync)
    assert _pyrun.own_python(main) == (str(main / ".venv" / "bin" / "python"), "")
    own = touch(wt, ".venv/bin/python")
    assert _pyrun.own_python(wt) == (str(own), "")
    assert sync.calls == []


def test_tree_python_prints_its_note_once(tmp_path, capsys):
    main, wt = checkout(tmp_path, lock=False)
    assert _pyrun.tree_python(wt, "pt_review") == str(main / ".venv" / "bin" / "python")
    _pyrun.tree_python(wt, "pt_review")
    assert capsys.readouterr().err == (
        f"pt_review: {base(main, wt)}, and {wt} has no uv.lock for an environment of its own; "
        f"this check may import that folder's package, not {wt}'s (#1145)\n")


def test_server_runner_asks_tree_python(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(_pyrun, "tree_python", lambda root, prog: asked.append((root, prog)) or "/tree/.venv/bin/python")

    def popen(cmd, *a, **k):
        asked.append(cmd[0])
        raise Stop

    monkeypatch.setattr(pt_review.subprocess, "Popen", popen)
    monkeypatch.setattr(pt_review.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    with pytest.raises(Stop):
        pt_review.ServerHandle(tmp_path, "app:main", None, timeout=1)
    assert asked == [(tmp_path, "pt_review"), "/tree/.venv/bin/python"]


# A stand-in for uv: `sync --frozen --project P` builds P/.venv as a real venv whose .pth names
# P/packages/lib/src, as an editable install of a workspace member does; every call is logged.
FAKE_UV = r'''
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
with open(Path(__file__).with_name("uv-calls.txt"), "a") as f:
    f.write(" ".join(args) + "\n")
if args[:1] != ["sync"]:
    sys.exit(2)
project = Path(args[args.index("--project") + 1])
subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(project / ".venv")], check=True)
site = next((project / ".venv" / "lib").glob("python3*/site-packages"))
(site / "lib1145.pth").write_text(str(project / "packages" / "lib" / "src") + "\n")
'''


def editable_checkout(tmp_path):
    """A main checkout whose real .venv holds a .pth naming main's packages/lib/src (outside the src and root
    paths pt_review and probe_run put first), and a uv worktree nested in it whose member differs."""
    main = tmp_path.resolve() / "main"
    touch(main, f"{LIB}/lib1145/__init__.py", "def where():\n    return 'main'\n")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(main / ".venv")], check=True, capture_output=True)
    site = next((main / ".venv" / "lib").glob("python3*/site-packages"))
    (site / "lib1145.pth").write_text(str(main / LIB) + "\n")
    wt = linked(main, main / ".claude" / "worktrees" / "wt")
    touch(wt, "pyproject.toml", "[project]\nname = 'x'\n")
    touch(wt, "uv.lock")
    touch(wt, f"{LIB}/lib1145/__init__.py", "def where(x):\n    return 'tree'\n")
    return main, wt


def fake_uv_on_path(tmp_path, monkeypatch):
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    (bindir / "fake_uv.py").write_text(FAKE_UV)
    uv = bindir / "uv"
    uv.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bindir / "fake_uv.py"}" "$@"\n')
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return bindir / "uv-calls.txt"


@posix_only
def test_pt_review_introspects_the_worktree_package(tmp_path, monkeypatch):
    main, wt = editable_checkout(tmp_path)
    calls = fake_uv_on_path(tmp_path, monkeypatch)
    got = pt_review.read_real(wt, [("lib1145", ["where"])])
    assert got[0]["ok"], got
    assert [p["name"] for p in got[0]["params"]] == ["x"]
    assert Path(got[0]["file"]).resolve().is_relative_to(wt)
    assert calls.read_text() == f"sync --frozen --project {wt}\n"


@posix_only
def test_probe_worker_runs_the_worktree_interpreter(tmp_path, monkeypatch):
    main, wt = editable_checkout(tmp_path)
    fake_uv_on_path(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location("probe_run_1145_mod", PROBE_RUN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real_tmp, real_popen, seen = mod.tempfile.NamedTemporaryFile, subprocess.Popen, {}
    monkeypatch.setattr(mod.tempfile, "NamedTemporaryFile", lambda **kw: real_tmp(dir=tmp_path, **kw))

    def popen(cmd, *a, **k):
        if "--worker" not in cmd:  # the uv sync and the venv build run for real
            return real_popen(cmd, *a, **k)
        seen["cmd"] = cmd
        raise Stop

    monkeypatch.setattr(mod.subprocess, "Popen", popen)
    cfg = types.SimpleNamespace(root=wt, adapter=wt / "adapter.py", timeout=5.0, stats_lock=None, workers_started=0)
    with pytest.raises(Stop):
        mod.Worker(cfg)
    py = seen["cmd"][0]
    assert py == str(wt / ".venv" / "bin" / "python")
    r = real_popen([py, "-c", "import inspect, lib1145; print(lib1145.__file__, inspect.signature(lib1145.where))"],
                   cwd=wt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = r.communicate(timeout=60)
    assert r.returncode == 0, err
    assert out.split() == [str(wt / LIB / "lib1145" / "__init__.py"), "(x)"]
