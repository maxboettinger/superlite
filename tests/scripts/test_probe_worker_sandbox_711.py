# tests/scripts/test_probe_worker_sandbox_711.py
"""#711: the probe worker drops credential variables and hands the adapter its temp folder; the template's run is sandboxed."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBES = ROOT / "skills" / "subagent-driven-development" / "probes"
DROP = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR",
        "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GIT_ASKPASS", "SSH_ASKPASS", "GIT_CONFIG_GLOBAL")
SHOW = ("import json, os, sys\n"
        f"keys = {('HOME', 'PYTHONPATH', 'KEEP_ME') + DROP!r}\n"
        "print(json.dumps({'cwd': os.getcwd(), 'argv': sys.argv[1:], 'env': {k: os.environ.get(k) for k in keys}}))\n")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pr = load("probe_run_sandbox_711", PROBES / "probe_run.py")


def test_drop_lists_agree():
    assert pr.SANDBOX_DROP == DROP
    assert load("adapter_template_drop_711", PROBES / "adapter_template.py").SANDBOX_DROP == DROP


def test_worker_env_drops_credentials(monkeypatch):
    monkeypatch.setenv("KEEP_ME", "kept")
    for k in DROP:
        monkeypatch.setenv(k, "secret")
    env = pr.worker_env(7.0)
    assert not set(DROP) & set(env)
    assert env["KEEP_ME"] == "kept" and env["SUPERLITE_PROBE_TIMEOUT"] == "7.0"
    assert env["PYTHONIOENCODING"] == "utf-8" and env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_template_run_is_sandboxed(tmp_path, monkeypatch):
    script = tmp_path / "show.py"
    script.write_text(SHOW, encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "realhome"))
    monkeypatch.delenv("SUPERLITE_PROBE_SANDBOX", raising=False)
    monkeypatch.setenv("KEEP_ME", "kept")
    for k in DROP:
        monkeypatch.setenv(k, "secret")
    tpl = load("adapter_template_run_711", PROBES / "adapter_template.py")
    monkeypatch.setattr(tpl, "CLI", [sys.executable, str(script)])
    rc, out, err = tpl.run(["--x"], "")
    assert rc == 0, err
    got = json.loads(out)
    cwd, home = Path(os.path.realpath(got["cwd"])), Path(os.path.realpath(got["env"]["HOME"]))
    assert cwd.name == "cwd" and home.name == "home" and cwd.parent == home.parent
    assert cwd != Path(os.path.realpath(os.getcwd()))
    assert got["env"]["KEEP_ME"] == "kept" and {k: got["env"][k] for k in DROP} == {k: None for k in DROP}
    assert str(tpl.ROOT) in got["env"]["PYTHONPATH"].split(os.pathsep)
    assert got["argv"] == ["--x"]


def test_worker_hands_the_adapter_its_temp_folder(tmp_path):
    seen = tmp_path / "seen"
    seen.mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    adapter = root / "adapter.py"
    adapter.write_text(
        "import json, os\n"
        f"SEEN = {str(seen)!r}\n"
        "def run(args, stdin):\n"
        "    box = os.environ.get('SUPERLITE_PROBE_SANDBOX')\n"
        "    with open(os.path.join(SEEN, '%d.json' % os.getpid()), 'w') as f:\n"
        "        json.dump({'box': box, 'isdir': bool(box) and os.path.isdir(box),\n"
        "                   'leaked': [k for k in ('GH_TOKEN', 'GITHUB_TOKEN', 'SSH_AUTH_SOCK') if k in os.environ]}, f)\n"
        "    return 0, 'ok', ''\n", encoding="utf-8")
    env = dict(os.environ, GH_TOKEN="secret", GITHUB_TOKEN="secret", SSH_AUTH_SOCK=str(tmp_path / "agent.sock"))
    p = subprocess.run([sys.executable, str(PROBES / "probe_run.py"), "--adapter", str(adapter), "--root", str(root)],
                       capture_output=True, text=True, timeout=300, env=env)
    files = sorted(seen.glob("*.json"))
    assert files, p.stdout + p.stderr
    for f in files:
        got = json.loads(f.read_text(encoding="utf-8"))
        assert got["isdir"] and got["leaked"] == [], got
        assert Path(got["box"]).name.startswith("probe-") and not Path(got["box"]).exists()
