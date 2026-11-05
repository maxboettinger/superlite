# tests/scripts/test_fleet_layer.py
import json, sys, types
from pathlib import Path
import pytest
from test_herdr_client import fake  # noqa: F401  (fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_layer as fl  # noqa: E402
import herdr_client as hc  # noqa: E402

class Pane:
    def __init__(self): self.calls = []; self.closed = []
    def close_pane(self, pane_id): self.closed.append(pane_id)
    def run_in_pane(self, pane_id, command): self.calls.append((pane_id, command)); return ""

@pytest.fixture
def run_world(tmp_path, monkeypatch):
    root = tmp_path / "repo"; sd = root / ".superlite"; sd.mkdir(parents=True)
    (root / "scripts").mkdir(); (root / "scripts" / "test_layers.py").write_text("# layers\n")
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {}, "next": 5}))
    seen = {}
    def choose(sd_, model, env):
        seen["choose"] = (Path(sd_), model); return ("claude3", "/u/.claude-account3", "claude3")
    def open_pane(sd_, wid, cwd, env, record):
        seen["open"] = (wid, cwd, env, record)
        data = json.loads((sd / "fleet.json").read_text()); data["workers"][wid] = {**record, "pane_id": "w6:p2"}
        (sd / "fleet.json").write_text(json.dumps(data)); return "w6:p2"
    monkeypatch.setattr(fl.fleet, "choose_account", choose, raising=False)
    monkeypatch.setattr(fl.fleet, "open_pane", open_pane, raising=False)
    pane = Pane(); monkeypatch.setattr(fl, "hc", pane)
    return types.SimpleNamespace(root=root, sd=sd, seen=seen, pane=pane)

def test_run_opens_a_shell_pane_with_the_account_and_no_superlite_env(run_world):
    base = {"HOME": "/u", "SUPERLITE_STATE_DIR": "/x", "SUPERLITE_FLEET_WORKER": "W9", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/u/.claude/plugins"}
    r = fl.run(run_world.sd, "headless", run_world.root, env=base)
    wid, cwd, env, record = run_world.seen["open"]
    assert wid == "W5" and cwd == str(run_world.root) and run_world.seen["choose"] == (run_world.sd, None)
    assert env == {"CLAUDE_CONFIG_DIR": "/u/.claude-account3", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/u/.claude/plugins"}
    assert {k: record[k] for k in ("role", "layer", "account", "state", "task", "one_turn")} == {
        "role": "layer", "layer": "headless", "account": "claude3", "state": "busy", "task": "layer-headless", "one_turn": True}
    assert isinstance(record["sent"], int) and record["sent"] > 10 ** 12
    (pane, command), = run_world.pane.calls
    log = run_world.sd / "fleet" / "layers" / "W5-headless.log"; ex = run_world.sd / "fleet" / "layers" / "W5-headless.exit"
    assert pane == "w6:p2" and "-u scripts/test_layers.py run headless" in command and "echo $?" in command
    assert str(log) in command and str(ex) in command and command.startswith("cd ")
    assert r == {"id": "W5", "account": "claude3", "pane_id": "w6:p2", "layer": "headless", "log": str(log), "exit": str(ex)}

def test_main_lines_and_refusals(run_world, monkeypatch, capsys):
    monkeypatch.setattr(fl.state, "resolve", lambda plan=None: str(run_world.sd))
    monkeypatch.setattr(fl.state, "git_root", lambda p: str(run_world.root))
    assert fl.main(["--layer", "tui"]) == 0
    assert capsys.readouterr().out.strip() == "W5 layer-tui started account=claude3 pane=w6:p2"
    assert fl.main(["--layer", "unit"]) == 2 and "unknown layer unit (headless, tui, evals)" in capsys.readouterr().err
    (run_world.root / "scripts" / "test_layers.py").unlink()
    assert fl.main(["--layer", "headless"]) == 2 and "no scripts/test_layers.py" in capsys.readouterr().err

def test_blocked_account_choice_opens_nothing(run_world, monkeypatch):
    def blocked(sd_, model, env):
        print("BLOCKED: no account with headroom"); raise SystemExit(3)
    monkeypatch.setattr(fl.fleet, "choose_account", blocked, raising=False)
    with pytest.raises(SystemExit) as e:
        fl.run(run_world.sd, "headless", run_world.root, env={"HOME": "/u"})
    assert e.value.code == 3 and not run_world.pane.calls and "open" not in run_world.seen

def test_result_reads_exit_file_and_last_line(tmp_path):
    sd = tmp_path / ".superlite"; d = sd / "fleet" / "layers"; d.mkdir(parents=True)
    w = {"role": "layer", "layer": "headless"}
    assert fl.result(sd, "W5", w) is None
    (d / "W5-headless.log").write_text("headless: green\n\n"); (d / "W5-headless.exit").write_text("")
    assert fl.result(sd, "W5", w) is None
    (d / "W5-headless.exit").write_text("0\n")
    assert fl.result(sd, "W5", w) == {"status": "GREEN", "exit": 0, "last": "headless: green", "log": str(d / "W5-headless.log")}
    (d / "W5-headless.log").write_text("headless: red\n" + "x\n" * 30 + "FAILED tests/e2e/test_headless.py::test_x - assert 1 == 2\n")
    (d / "W5-headless.exit").write_text("1\n")
    assert fl.result(sd, "W5", w) == {"status": "RED", "exit": 1, "last": "FAILED tests/e2e/test_headless.py::test_x - assert 1 == 2",
                                      "log": str(d / "W5-headless.log")}
    (d / "W5-headless.log").unlink()
    assert fl.result(sd, "W5", w)["last"] == "(no log)"

def test_run_in_pane_argv(fake):
    assert hc.run_in_pane("w6:p2", "cd /r && echo hi") == '{"result": {"type": "ok"}}\n'
    assert fake()[0] == ["pane", "run", "w6:p2", "cd /r && echo hi"]

def test_herdr_failure_prints_blocked_and_frees_the_worker(run_world, monkeypatch, capsys):
    def boom(pane_id, command): raise hc.HerdrError("not_found", "pane gone")
    monkeypatch.setattr(run_world.pane, "run_in_pane", boom)
    with pytest.raises(SystemExit) as e:
        fl.run(run_world.sd, "evals", run_world.root, env={"HOME": "/u"})
    assert e.value.code == 3 and capsys.readouterr().out.strip() == "BLOCKED: W5 layer evals not_found: pane gone"
    assert json.loads((run_world.sd / "fleet.json").read_text())["workers"]["W5"]["state"] == "blocked"
