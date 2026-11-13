"""#681: the batch start resolves one run config, passes it to the lead spawn and stamps its id on the batch."""
import json
import sys

from backlog_fixtures import batch as b
from test_backlog_run import bk, get, put  # noqa: F401  (bk is a fixture)
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import run_config  # noqa: E402


def spy(monkeypatch):
    mod, seen = sys.modules["fleet_lead"], []
    orig = mod.spawn_lead

    def spawn(main_sd, wt, model="opus", env=None, rc=None):
        seen.append((model, rc))
        return orig(main_sd, wt, model, env, rc)
    monkeypatch.setattr(mod, "spawn_lead", spawn)
    return seen


def go(capsys, *argv):
    rc = br.main(["start", *argv])
    o = capsys.readouterr()
    return rc, o.out, o.err


def test_start_stamps_config_id(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    put(bk, b("B1", ["a.py"]))
    seen = spy(monkeypatch)
    rc, out, err = go(capsys, "B1")
    want = run_config.resolve(None, bk.root)
    assert rc == 0
    assert get(bk, "B1")["run_config"] == want["id"]
    model, cfg = seen[0]
    assert model == "opus" and cfg["lead"]["effort"] == "xhigh"


def test_start_config_from_project_file(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    (bk.sd / "run-configs.json").write_text(json.dumps({"configs": {"low": {"lead": {"effort": "high"}}}}), encoding="utf-8")
    put(bk, b("B1", ["a.py"]))
    seen = spy(monkeypatch)
    rc, out, err = go(capsys, "B1", "--config", "low")
    assert rc == 0
    assert seen[0][1]["lead"]["effort"] == "high"
    assert get(bk, "B1")["run_config"].startswith("low-")


def test_unknown_config_refuses_before_spawn(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    put(bk, b("B1", ["a.py"]))
    seen = spy(monkeypatch)
    rc, out, err = go(capsys, "B1", "--config", "nope")
    assert rc == 2
    assert "BLOCKED: run config: run config nope: not defined; known: default" in out
    assert seen == []
    assert get(bk, "B1")["state"] == "planned"


def test_model_flag_overrides(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    put(bk, b("B1", ["a.py"]))
    seen = spy(monkeypatch)
    rc, out, err = go(capsys, "B1", "--model", "sonnet")
    assert rc == 0
    assert seen[0][0] == "sonnet" and seen[0][1]["lead"]["model"] == "sonnet"


def test_stdout_lines_unchanged(bk, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    put(bk, b("B1", ["a.py"]))
    rc, out, err = go(capsys, "B1", "--cap", "2")
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"
    assert out.splitlines() == [f"B1 running lead=W1 worktree={wt}"]
    assert err.startswith("run config: default-")
