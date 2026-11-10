"""probe_run: a run= entry's timeout is measured from its own start-up, so a uv-started CLI is no hang (#368)."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
PROBE_RUN = SDD / "probes" / "probe_run.py"
_spec = importlib.util.spec_from_file_location("probe_run_timeout_368", PROBE_RUN)
pr = importlib.util.module_from_spec(_spec)
sys.modules["probe_run_timeout_368"] = pr
_spec.loader.exec_module(pr)

ADAPTER = '''import os
import subprocess
import time

START = float(os.environ.get("FAKE_START", "0"))
LOG = os.environ["FAKE_LOG"]
GOOD_ARGS = []
GOOD_STDIN = ""


def run(args, stdin, timeout=10):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s %s\\n" % (",".join(args) or "-", timeout, os.environ.get("SUPERLITE_PROBE_TIMEOUT")))
    if not args and os.environ.get("FAKE_WARM_FAIL"):
        raise RuntimeError("cannot start")
    if args and args[0] == "boom":
        raise subprocess.TimeoutExpired("cli", 1.5)
    time.sleep(START + (float(args[0]) if args else 0.0))
    return 0, "ok", ""
'''

PROBES = '''from pack._common import P

CATEGORY = "slowstart"
PROBES = [P("arg_wait", "run", lambda n, ctx: ([ARG], ""))]
'''


def project(tmp_path: Path, arg: str) -> Path:
    root = tmp_path / "proj"
    (root / "probes").mkdir(parents=True)
    (root / "adapter.py").write_text(ADAPTER, encoding="utf-8")
    (root / "probes" / "slowstart.py").write_text(PROBES.replace("ARG", repr(arg)), encoding="utf-8")
    (root / "cli.py").write_text("print('cli')\n", encoding="utf-8")
    return root


def probe(root: Path, *extra: str, **env: str):
    log = root / "calls.log"
    p = subprocess.run([sys.executable, str(PROBE_RUN), "--adapter", str(root / "adapter.py"), "--root", str(root),
                        "--probes", str(root / "probes"), "--categories", "slowstart", "--files", "cli.py",
                        "--workers", "1", *extra],
                       capture_output=True, text=True, timeout=300, env={**os.environ, "FAKE_LOG": str(log), **env})
    res = json.loads((root / ".superlite" / "probes" / "probe-results.json").read_text(encoding="utf-8"))
    return p, res, (log.read_text(encoding="utf-8").splitlines() if log.exists() else [])


def test_run_timeout_from_start_up():
    assert pr.run_timeout_from(0.3) == 5.0
    assert pr.run_timeout_from(2.0) == 7.0
    assert pr.run_timeout_from(2.04) == 7.1
    assert pr.run_timeout_from(30.0) == 60.0


def test_timeout_for_uses_the_measured_run_timeout_and_the_cap():
    cfg = types.SimpleNamespace(timeout=None, run_timeout=7.0)
    assert pr.timeout_for({"entry": "run"}, cfg) == 7.0
    assert pr.timeout_for({"entry": "call"}, cfg) == 2.0
    assert pr.timeout_for({"entry": "request"}, cfg) == 10.0
    cfg.timeout = 3.0
    assert pr.timeout_for({"entry": "run"}, cfg) == 3.0 and pr.timeout_for({"entry": "call"}, cfg) == 2.0
    assert pr.timeout_for({"entry": "run"}, types.SimpleNamespace(timeout=None)) == 5.0


def test_slow_start_raises_the_run_timeout(tmp_path):
    root = project(tmp_path, "3.6")
    p, res, calls = probe(root, FAKE_START="2.0")
    assert p.returncode == 0, p.stdout + p.stderr
    warm = res["run_warmup"]
    assert warm["second"] >= 2.0 and 7.0 <= warm["timeout"] <= 9.0, warm
    assert res["stats"]["run_timeout"] == warm["timeout"]
    assert [x["status"] for x in res["probes"]] == ["pass"], res["probes"]
    assert res["stats"]["workers_started"] == 2
    assert calls[-1] == f"3.6 {warm['timeout']} {warm['timeout']}", calls


def test_fast_start_keeps_the_default(tmp_path):
    root = project(tmp_path, "0")
    p, res, calls = probe(root)
    assert p.returncode == 0, p.stdout + p.stderr
    assert res["run_warmup"]["timeout"] == 5.0 and res["stats"]["run_timeout"] == 5.0
    assert res["run_warmup"]["first"] < 2.0 and res["run_warmup"]["second"] < 2.0
    assert res["stats"]["workers_started"] == 1
    assert [c.split()[0] for c in calls] == ["-", "-", "0"], calls


def test_failed_warm_up_keeps_the_default_and_says_why(tmp_path):
    root = project(tmp_path, "0")
    p, res, _calls = probe(root, FAKE_WARM_FAIL="1")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "RuntimeError: cannot start" in res["run_warmup"]["error"]
    assert res["run_warmup"]["timeout"] == 5.0 and res["stats"]["run_timeout"] == 5.0
    assert [x["status"] for x in res["probes"]] == ["pass"]


def test_adapter_timeout_is_a_hang_not_a_crash(tmp_path):
    root = project(tmp_path, "boom")
    p, res, _calls = probe(root)
    assert p.returncode == 1
    one = res["probes"][0]
    assert one["status"] == "hang" and "adapter timed out after 1.5s" in one["message"], one
    assert [g["kind"] for g in res["failures"]] == ["hang"]


def test_cap_applies_to_the_measured_timeout(tmp_path):
    root = project(tmp_path, "0")
    p, res, _calls = probe(root, "--timeout", "3", FAKE_START="1.5")
    assert p.returncode == 0, p.stdout + p.stderr
    assert res["run_warmup"]["timeout"] == 3.0 and res["stats"]["run_timeout"] == 3.0


def test_no_run_probe_means_no_warm_up(tmp_path):
    root = project(tmp_path, "0")
    (root / "adapter.py").write_text("def call(text):\n    return text\n", encoding="utf-8")
    p, res, calls = probe(root)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "run_warmup" not in res and res["stats"]["run_timeout"] == 5.0 and calls == []


def test_template_reads_the_timeout_at_call_time():
    tree = ast.parse((SDD / "probes" / "adapter_template.py").read_text(encoding="utf-8"))
    funcs = {n.name: ast.unparse(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "SUPERLITE_PROBE_TIMEOUT" in funcs["_timeout"]
    assert "_timeout()" in funcs["run"] and "_timeout()" in funcs["request"]
    names = {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert "TIMEOUT" not in names
