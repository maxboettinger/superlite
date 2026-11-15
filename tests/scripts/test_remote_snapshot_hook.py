# tests/scripts/test_remote_snapshot_hook.py
import json, os, re, subprocess
from pathlib import Path
import pytest
from test_plan_tools import ROOT
HOOKS = ROOT / "hooks"
REF = "refs/superlite/remote/p/W2/stop"


def run_hook(name, stdin, env, cwd):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    e.update(env); e["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    return subprocess.run(["bash", str(HOOKS / name)], input=stdin, capture_output=True, text=True, env=e, cwd=cwd)


def git(cwd, *a):
    e = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, env=e, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"; sd = p / ".superlite"; sd.mkdir(parents=True); (sd / "stable.json").write_text("{}")
    git(p, "init", "-q"); (p / "a.py").write_text("base\n"); git(p, "add", "a.py"); git(p, "commit", "-qm", "b")
    (p / "a.py").write_text("edited\n")
    return p


def env(p, ref=REF):
    e = {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_AGENT": "superlite:implementer", "SUPERLITE_STATE_DIR": str(p / ".superlite")}
    if ref:
        e["SUPERLITE_REMOTE_SNAPSHOT"] = ref
    return e


def last(p):
    return (p / ".superlite" / "metrics.jsonl").read_text().splitlines()[-1]


def test_snapshot_in_record(proj):
    stdin = json.dumps({"transcript_path": "/t/w2.jsonl", "last_assistant_message": "Status: DONE", "cwd": str(proj)})
    r = run_hook("capture-worker-stop", stdin, env(proj), proj); assert r.returncode == 0
    line = last(proj); rec = json.loads(line)
    assert re.fullmatch(r"[0-9a-f]{40}", rec["snapshot"]) and line.endswith(',"snapshot":"' + rec["snapshot"] + '"}')
    assert git(proj, "rev-parse", REF) == rec["snapshot"]


def test_record_unchanged_without_ref(proj):
    r = run_hook("capture-worker-stop", json.dumps({"cwd": str(proj)}), env(proj, None), proj); assert r.returncode == 0
    assert "snapshot" not in json.loads(last(proj))
    assert last(proj).endswith('"last":""}')


def test_hook_never_blocks(proj, tmp_path):
    plain = tmp_path / "plain"; plain.mkdir()
    r = run_hook("capture-worker-stop", json.dumps({"cwd": str(plain)}), env(proj), proj)
    assert r.returncode == 0 and "snapshot" not in json.loads(last(proj))
    r = run_hook("capture-worker-stop", "", env(proj), plain)
    assert r.returncode == 0


def test_snapshot_runs_in_hook_cwd(proj, tmp_path):
    other = tmp_path / "other"; other.mkdir()
    run_hook("capture-worker-stop", json.dumps({"cwd": str(proj)}), env(proj), other)
    assert re.fullmatch(r"[0-9a-f]{40}", json.loads(last(proj)).get("snapshot", ""))
    run_hook("capture-worker-stop", "{}", env(proj, REF + "2"), proj)
    assert git(proj, "rev-parse", REF + "2")
