"""experiment arms (#682): per-batch config arms, state in experiments.json."""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment as ex  # noqa: E402
import report  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    r = tmp_path / "proj"
    (r / ".superlite").mkdir(parents=True)
    return r


def configs(root, **cfgs):
    (root / ".superlite" / "run-configs.json").write_text(json.dumps({"configs": cfgs}))


def store(root):
    return json.loads((root / ".superlite" / "experiments.json").read_text())


def cli(root, capsys, *argv):
    rc = ex.main([*argv[:1], "--root", str(root), *argv[1:]] if argv[0] in ("set", "next", "report") else list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def setup_cheap(root, capsys, batches="4", seed="7"):
    configs(root, cheap={"lead": {"model": "sonnet"}})
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,cheap", "--batches", batches, "--seed", seed)
    assert rc == 0, err
    return store(root)["experiments"]["e1"]


def test_set_refuses_two_factors(root, capsys):
    configs(root, two={"lead": {"model": "sonnet", "effort": "low"}})
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,two")
    assert rc == 2
    assert "error:" in err and "lead.effort" in err and "lead.model" in err and "--force" in err
    assert not (root / ".superlite" / "experiments.json").exists()
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,two", "--force")
    assert rc == 0, err
    assert store(root)["experiments"]["e1"]["factor"] == ["lead.effort", "lead.model"]


def test_next_same_batch_same_arm(root, capsys):
    setup_cheap(root, capsys)
    _, o1, _ = cli(root, capsys, "next", "--batch", "B1")
    _, o2, _ = cli(root, capsys, "next", "--batch", "B1")
    assert o1 == o2
    assert len(store(root)["experiments"]["e1"]["assigned"]) == 1


def test_corrupt_store_refuses(root, capsys):
    configs(root, cheap={"lead": {"model": "sonnet"}})
    p = root / ".superlite" / "experiments.json"
    p.write_text("[")
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,cheap")
    assert rc == 2
    assert err.startswith("error:") and "experiments.json" in err
    assert p.read_text() == "["


def test_set_two_arms_one_factor(root, capsys):
    e = setup_cheap(root, capsys)
    s = store(root)
    assert s["active"] == "e1"
    assert e["factor"] == ["lead.model"]
    assert len(e["order"]) == 4
    assert e["order"][0] != e["order"][1] and e["order"][0] == e["order"][2]
    assert e["configs"]["cheap"].startswith("cheap-")
    assert e["margin"] == 10.0 and e["min_per_arm"] == 5


def test_set_refuses_identical(root, capsys):
    configs(root, same={})
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,same")
    assert rc == 2 and "same config" in err


def test_set_refuses_unknown_arm(root, capsys):
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,nope")
    assert rc == 2 and "nope" in err


def test_set_refuses_second_active(root, capsys):
    setup_cheap(root, capsys)
    rc, _, err = cli(root, capsys, "set", "--id", "e2", "--arms", "default,cheap")
    assert rc == 2 and "e1" in err


def test_set_refuses_reused_id(root, capsys):
    setup_cheap(root, capsys, batches="1")
    cli(root, capsys, "next", "--batch", "B1")
    assert store(root)["active"] is None
    rc, _, err = cli(root, capsys, "set", "--id", "e1", "--arms", "default,cheap")
    assert rc == 2 and "e1" in err


def test_arms_with_prime_refuses(root, capsys):
    configs(root, cheap={"lead": {"model": "sonnet"}})
    rc, _, err = cli(root, capsys, "set", "--id", "x", "--arms", "default,cheap", "--prime", "full")
    assert rc == 2 and "error:" in err


def test_next_last_batch_again_same_arm(root, capsys):
    e = setup_cheap(root, capsys)
    for i in range(1, 5):
        cli(root, capsys, "next", "--batch", f"B{i}")
    rc, out, _ = cli(root, capsys, "next", "--batch", "B4")
    arm = e["order"][3]
    assert rc == 0
    assert f"B4 arm={arm}:" in out
    assert "no active experiment" not in out


def test_next_alternates_and_ends(root, capsys):
    e = setup_cheap(root, capsys)
    for i in range(1, 5):
        rc, out, _ = cli(root, capsys, "next", "--batch", f"B{i}")
        arm = e["order"][i - 1]
        assert rc == 0
        assert f"B{i} arm={arm}: sl backlog start B{i} --config {arm}" in out
        assert ("experiment e1: all 4 batches assigned; ended" in out) == (i == 4)
    assert store(root)["active"] is None
    rc, out, _ = cli(root, capsys, "next", "--batch", "B5")
    assert rc == 0 and "no active experiment" in out


def test_random_start_by_seed(root):
    configs(root, cheap={"lead": {"model": "sonnet"}})
    firsts = set()
    for seed in range(20):
        r = root / f"s{seed}"
        (r / ".superlite").mkdir(parents=True)
        configs(r, cheap={"lead": {"model": "sonnet"}})
        firsts.add(ex.set_arms(r, "e", ["default", "cheap"], seed=seed)["order"][0])
    assert firsts == {"default", "cheap"}
    r1, r2 = root / "a", root / "b"
    for r in (r1, r2):
        (r / ".superlite").mkdir(parents=True)
        configs(r, cheap={"lead": {"model": "sonnet"}})
    assert ex.set_arms(r1, "e", ["default", "cheap"], seed=3)["order"] == ex.set_arms(r2, "e", ["default", "cheap"], seed=3)["order"]


def test_assignment_after_end(root, capsys):
    e = setup_cheap(root, capsys)
    for i in range(1, 5):
        cli(root, capsys, "next", "--batch", f"B{i}")
    assert ex.assignment(root, "B3") == {"experiment": "e1", "arm": e["order"][2]}
    assert ex.assignment(root, "B9") is None
    assert ex.assign(root, "B9") is None
    assert ex.load_arms(root, "e1")["id"] == "e1" and ex.load_arms(root, "zz") is None


def test_assign_shape(root, capsys):
    e = setup_cheap(root, capsys)
    assert ex.assign(root, "B12") == {"experiment": "e1", "arm": e["order"][0], "config": e["order"][0]}


def test_config_diff():
    a = {"lead": {"model": "opus", "effort": "xhigh"}, "cache_ttl": {}, "workers": {}}
    b = {"lead": {"model": "sonnet", "effort": "xhigh"}, "cache_ttl": {}, "workers": {}}
    assert ex.config_diff(a, b) == ["lead.model"]
    assert ex.config_diff(a, a) == []


def test_report_cli_uses_report(root, capsys, monkeypatch, tmp_path):
    seen = {}

    def fake(rows, exp):
        seen["rows"], seen["exp"] = rows, exp
        return {"verdict": "v"}

    monkeypatch.setattr(report, "experiment_report", fake, raising=False)
    monkeypatch.setattr(report, "experiment_text", lambda rep: "TEXT\n", raising=False)
    setup_cheap(root, capsys)
    rc, out, _ = cli(root, capsys, "report", "e1")
    assert rc == 0 and out.strip() == "TEXT"
    rc, out, _ = cli(root, capsys, "report", "e1", "--json")
    assert json.loads(out)["verdict"] == "v"
    rc, _, err = cli(root, capsys, "report", "e9")
    assert rc == 2 and "e9" in err
    rows = [{"experiment": "r1", "arms": ["default", "cheap"], "batch": "B1"}]
    f = tmp_path / "rows.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    rc, _, err = cli(root, capsys, "report", "r1", "--rows", str(f))
    assert rc == 0, err
    assert seen["exp"]["arms"] == ["default", "cheap"] and seen["exp"]["margin"] == 10.0
    assert seen["exp"]["min_per_arm"] == 3 and seen["rows"] == rows
    cli(root, capsys, "report", "r1", "--rows", str(f), "--margin", "5", "--min", "2")
    assert seen["exp"]["margin"] == 5.0 and seen["exp"]["min_per_arm"] == 2


def test_report_refuses_seed_option(root, capsys):
    setup_cheap(root, capsys)
    with pytest.raises(SystemExit) as e:
        cli(root, capsys, "report", "e1", "--seed", "3")
    assert e.value.code == 2
