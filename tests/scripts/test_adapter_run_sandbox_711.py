# tests/scripts/test_adapter_run_sandbox_711.py
"""#711: the generated adapter's run= starts the planned command in a scratch HOME and working folder, without credential variables."""
from __future__ import annotations

import importlib.util
import json
import os
import site
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
_spec = importlib.util.spec_from_file_location("pt_review_sandbox_711", SDD / "scripts" / "pt_review.py")
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_sandbox_711"] = pt
_spec.loader.exec_module(pt)

DROP = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR",
        "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GIT_ASKPASS", "SSH_ASKPASS", "GIT_CONFIG_GLOBAL")
KEYS = ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "PWD", "GIT_TERMINAL_PROMPT", "GIT_CONFIG_NOSYSTEM",
        "PYTHONUSERBASE", "KEEP_ME") + DROP
SHOW = ("import json, os, sys\n"
        f"keys = {KEYS!r}\n"
        "print(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:], 'env': {k: os.environ.get(k) for k in keys}}))\n")


def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
    for rel in ("show.py", "tools/show.py", "tools/__main__.py"):
        (root / rel).write_text(SHOW, encoding="utf-8")
    return root


def adapter(root: Path, entry: str):
    plan = root / "plan.md"
    plan.write_text(f"# p\n\n**Probe entry:** {entry}\n", encoding="utf-8")
    assert pt.main(["adapter", "--plan", str(plan), "--root", str(root)]) == 0
    spec = importlib.util.spec_from_file_location(f"adapter_711_{abs(hash((str(root), entry)))}",
                                                  root / ".superlite" / "probes" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shown(mod, *args) -> dict:
    rc, out, err = mod.run(list(args))
    assert rc == 0, err
    return json.loads(out)


def real(p) -> Path:
    return Path(os.path.realpath(p))


@pytest.fixture
def secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "realhome"))
    monkeypatch.delenv("SUPERLITE_PROBE_SANDBOX", raising=False)
    monkeypatch.setenv("KEEP_ME", "kept")
    for k in DROP:
        monkeypatch.setenv(k, "secret")


def test_run_has_scratch_home_cwd_and_no_credentials(tmp_path, secrets):
    root = project(tmp_path)
    out = shown(adapter(root, "run=python tools/show.py"), "--flag")
    cwd, env = real(out["cwd"]), out["env"]
    home = real(env["HOME"])
    assert cwd.name == "cwd" and home.name == "home" and cwd.parent == home.parent
    assert cwd != real(root) and real(root) not in cwd.parents
    assert real(env["XDG_CONFIG_HOME"]) == home / ".config" and real(env["XDG_CACHE_HOME"]) == home / ".cache"
    assert real(env["PWD"]) == cwd
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["KEEP_ME"] == "kept"
    assert {k: env[k] for k in DROP} == {k: None for k in DROP}
    assert out["argv"] == ["--flag"]


def test_planned_paths_resolve_against_the_root(tmp_path, secrets):
    root = project(tmp_path)
    for entry in ("run=python show.py", "run=python -m tools"):
        assert real(shown(adapter(root, entry))["cwd"]).name == "cwd", entry
    out = shown(adapter(root, "run=python tools/show.py --config=tools/show.py"), "tools/show.py")
    assert out["argv"] == ["--config=" + str(real(root) / "tools" / "show.py"), "tools/show.py"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bit")
def test_relative_executable_runs_from_the_root(tmp_path, secrets):
    root = project(tmp_path)
    exe = root / "bin" / "show"
    exe.parent.mkdir()
    exe.write_text(f"#!{sys.executable}\n" + SHOW, encoding="utf-8")
    exe.chmod(0o755)
    assert real(shown(adapter(root, "run=bin/show"))["cwd"]).name == "cwd"


def test_scratch_folders_live_under_the_probe_run_folder(tmp_path, secrets, monkeypatch):
    box = tmp_path / "worker-tmp"
    box.mkdir()
    monkeypatch.setenv("SUPERLITE_PROBE_SANDBOX", str(box))
    out = shown(adapter(project(tmp_path), "run=python tools/show.py"))
    assert real(box) in real(out["cwd"]).parents and real(box) in real(out["env"]["HOME"]).parents


def test_scratch_folders_are_made_once_per_process(tmp_path, secrets):
    mod = adapter(project(tmp_path), "run=python tools/show.py")
    a, b = shown(mod), shown(mod)
    assert a["cwd"] == b["cwd"] and a["env"]["HOME"] == b["env"]["HOME"]


def test_python_user_base_is_kept(tmp_path, secrets, monkeypatch):
    monkeypatch.delenv("PYTHONUSERBASE", raising=False)
    root = project(tmp_path)
    assert shown(adapter(root, "run=python tools/show.py"))["env"]["PYTHONUSERBASE"] == site.getuserbase()
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path / "ub"))
    assert shown(adapter(root, "run=python show.py"))["env"]["PYTHONUSERBASE"] == str(tmp_path / "ub")


def test_drop_list_is_the_planned_one(tmp_path):
    assert adapter(project(tmp_path), "run=python show.py").SANDBOX_DROP == DROP


def test_code_token_after_dash_c_is_not_rooted(tmp_path, secrets):
    mod = adapter(project(tmp_path), 'run=python -c "import sys; print(1/2)"')
    rc, out, err = mod.run([])
    assert (rc, out.strip()) == (0, "0.5"), err
