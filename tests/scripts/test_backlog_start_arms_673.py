# tests/scripts/test_backlog_start_arms_673.py
import json, sys
import pytest
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as real_bb  # noqa: E402
import backlog_run as br  # noqa: E402
import experiment  # noqa: E402
import run_config  # noqa: E402


@pytest.fixture
def cfg(bk, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    spawned = []
    real = sys.modules["fleet_lead"].spawn_lead
    def spy(sd, wt, model="opus", env=None, rc=None):
        spawned.append((wt.name, rc))
        return real(sd, wt, model, env, rc)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", spy)
    bk.spawned = spawned
    def write(configs):
        (bk.sd / "run-configs.json").write_text(json.dumps({"configs": configs}))
    bk.write = write
    return bk


def test_start_lean_config_yields_lean_brief(cfg, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "backlog_brief", real_bb)
    cfg.write({"lean1": {"lead": {"text": "lean"}}})
    put(cfg, b("B1", ["a.py"], issues=[7]))
    assert run(capsys, "start", "B1", "--config", "lean1")[0] == 0
    wt = cfg.root / ".claude" / "worktrees" / "superlite-b1-t"
    seen = (wt / ".superlite" / "briefs" / "lead.md").read_text()
    batch = get(cfg, "B1")
    ctx = {"sl": str(br.HERE / "sl"), "backlog_md": str(br.HERE.parent / "backlog.md"), "repo": "o/r", "approved": batch and get(cfg, "B1") and br.bs.load(br.bs.path(cfg.root))["approved_ship"],
           "titles": {}, "summaries": [], "resume": False, "worktree": str(wt), "text": "lean"}
    assert seen.startswith(real_bb.lead_brief({**batch, "state": "planned"}, ctx).split("\n")[0])
    assert real_bb.LEAN_BUILD.format(sl=str(br.HERE / "sl")) in seen


def test_start_text_from_default_config(cfg, capsys, monkeypatch):
    got = []
    monkeypatch.setitem(sys.modules, "backlog_brief", type(sys)("bb"))
    sys.modules["backlog_brief"].lead_brief = lambda batch, ctx: got.append(ctx.get("text")) or "brief"
    put(cfg, b("B1", ["a.py"]))
    assert run(capsys, "start", "B1")[0] == 0
    assert got == [run_config.resolve(None, cfg.root)["lead"].get("text")]


def test_start_assigns_alternating_arms(cfg, capsys):
    cfg.write({"armA": {"lead": {"effort": "high"}}, "armB": {"lead": {"effort": "medium"}}})
    experiment.set_arms(cfg.root, "E1", ["armA", "armB"], batches=2, min_per_arm=1, seed=1)
    put(cfg, b("B1", ["a.py"]), b("B2", ["b.py"]))
    assert run(capsys, "start", "--cap", "2")[0] == 0
    arms = {}
    for bid in ("B1", "B2"):
        x = get(cfg, bid)
        assert x["experiment"] == "E1" and x["arm"] in ("armA", "armB") and x["run_config"].startswith(x["arm"])
        arms[bid] = x["arm"]
    assert set(arms.values()) == {"armA", "armB"}
    eff = {"armA": "high", "armB": "medium"}
    for name, rc in cfg.spawned:
        bid = "B1" if "b1" in name else "B2"
        assert rc["lead"]["effort"] == eff[arms[bid]]


def test_start_config_flag_skips_experiment(cfg, capsys):
    cfg.write({"armA": {"lead": {"effort": "high"}}, "armB": {"lead": {"effort": "medium"}}})
    experiment.set_arms(cfg.root, "E1", ["armA", "armB"], batches=2, min_per_arm=1, seed=1)
    put(cfg, b("B1", ["a.py"]))
    assert run(capsys, "start", "B1", "--config", "armA")[0] == 0
    assert "arm" not in get(cfg, "B1") and "experiment" not in get(cfg, "B1")
    store = json.loads((cfg.sd / "experiments.json").read_text())
    assert store["experiments"]["E1"]["assigned"] == {}


def test_start_corrupt_experiment_store_blocks_batch(cfg, capsys):
    (cfg.sd / "experiments.json").write_text("not json")
    put(cfg, b("B1", ["a.py"]))
    rc, out = run(capsys, "start", "B1")
    assert rc == 2 and out.startswith("BLOCKED: B1 not started: experiment: ")
    assert get(cfg, "B1")["state"] == "planned" and not cfg.spawned


def test_start_arm_config_unknown_blocks_batch(cfg, capsys, monkeypatch):
    put(cfg, b("B1", ["a.py"]))
    monkeypatch.setattr(experiment, "assign", lambda root, bid: {"experiment": "E1", "arm": "nope", "config": "nope"})
    rc, out = run(capsys, "start", "B1")
    assert rc == 2 and out.startswith("BLOCKED: B1 not started: run config: ")
    assert get(cfg, "B1")["state"] == "planned" and not cfg.spawned
