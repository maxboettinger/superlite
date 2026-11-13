# tests/scripts/test_fleet_run_config_681.py: the active run config shapes workers (#681)
import json
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import run_config  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")
TTL = "CLAUDE_CODE_PROMPT_CACHE_TTL"

def _snap(world, **over):
    cfg = run_config.resolve(overrides=over or None)
    run_config.write_active(world.sd, cfg)
    return cfg

def _starts(world):
    return [c for c in world.fh.calls if c[0] == "start_agent"]

def _worker(world, wid="W1"):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]

def test_with_model_replaces_inserts_prepends():
    A = ["--agent", "superlite:final-reviewer", "--effort", "high", "--disallowedTools", "AskUserQuestion"]
    assert fleet.with_model(A, "sonnet") == ["--agent", "superlite:final-reviewer", "--model", "sonnet", "--effort", "high", "--disallowedTools", "AskUserQuestion"]
    assert fleet.with_model(["--agent", "superlite:implementer", "--model", "sonnet"], "opus") == ["--agent", "superlite:implementer", "--model", "opus"]
    assert fleet.with_model(["--effort", "high"], "opus") == ["--model", "opus", "--effort", "high"]

def test_worker_ttl_from_snapshot(world):
    fleet.main(["on"])
    _snap(world, cache_ttl={"workers": "5m"})
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _worker(world)["launch"]["env"][TTL] == "5m"
    assert _worker(world)["launch"]["env"][TTL] == "5m"

def test_worker_ttl_default_without_snapshot(world):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _worker(world)["launch"]["env"][TTL] == "1h"

def test_role_pin(world, capsys):
    fleet.main(["on"])
    _snap(world, workers={"final-reviewer": "sonnet"})
    fleet.spawn(world.sd, world.plan, None, world.proj, role="final-reviewer")
    argv = _starts(world)[0][2]
    assert argv.count("--model") == 1 and argv[argv.index("--model") + 1] == "sonnet"
    assert any(json.loads(l).get("model") == "sonnet" for l in (world.sd / "metrics.jsonl").read_text().splitlines())
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _starts(world)[1][2][_starts(world)[1][2].index("--model") + 1] == "sonnet"
    fleet.spawn(world.sd, world.plan, "haiku", world.proj)
    argv = _starts(world)[2][2]
    assert argv[argv.index("--model") + 1] == "haiku"

def test_haiku_tier_keeps_haiku_prime(world, capsys):
    fleet.main(["on"])
    _snap(world, workers={"implementer": "sonnet"})
    (world.sd / "prime-haiku.md").unlink()
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "haiku", world.proj)
    assert e.value.code == 3 and "prime-haiku.md" in capsys.readouterr().out

def test_record_run_config(world):
    fleet.main(["on"])
    cfg = _snap(world)
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _worker(world)["run_config"] == cfg["id"]

def test_on_config_writes_snapshot(world):
    (world.sd / "run-configs.json").write_text(json.dumps({"configs": {"low": {"lead": {"effort": "high"}}}}))
    assert fleet.main(["on", "--config", "low", "--plan", str(world.sd)]) == 0
    snap = json.loads((world.sd / "run-config.json").read_text())
    assert snap["name"] == "low" and snap["lead"]["effort"] == "high"

def test_on_bad_config_exits_2(world, capsys):
    assert fleet.main(["on", "--config", "nope", "--plan", str(world.sd)]) == 2
    assert "error: run config nope: not defined; known: default" in capsys.readouterr().err
    assert not (world.sd / "run-config.json").exists()
    assert not fleet.fs.is_on(world.sd)

def test_on_without_config_keeps_snapshot(world):
    cfg = _snap(world, cache_ttl={"workers": "5m"})
    assert fleet.main(["on", "--plan", str(world.sd)]) == 0
    assert json.loads((world.sd / "run-config.json").read_text()) == cfg
