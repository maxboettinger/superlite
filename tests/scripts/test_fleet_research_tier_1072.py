# tests/scripts/test_fleet_research_tier_1072.py: research --tier maps fixing.md's tiers; an unknown tier is refused (#1072)
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402
from test_fleet import world  # noqa: E402,F401
import fleet  # noqa: E402

CFG = routing.load_cfg()
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("tier,model,effort", [
    (None, "sonnet", "low"), ("", "sonnet", "low"), ("1", "sonnet", "low"), ("sonnet", "sonnet", "low"),
    ("2", "sonnet", "high"), ("sonnet-high", "sonnet", "high"),
    ("3", "opus", "low"), ("opus", "opus", "low"), ("haiku", "haiku", "low")])
def test_research_tier_maps_to_a_model(tier, model, effort):
    r = fr.launch("research", tier, CFG)
    assert (r["agent"], r["model"], r["effort"]) == ("superlite:researcher", model, effort)
    assert r["argv"] == ["--agent", "superlite:researcher", "--model", model, "--effort", effort] + fr.RESEARCH_TAIL
    assert r["one_turn"] and not r["prime"] and not r["pool"]


@pytest.mark.parametrize("tier", ["4", "0", "fast", "Opus", "claude-opus-5-5"])
def test_research_unknown_tier_is_refused_naming_the_valid_tiers(tier):
    with pytest.raises(ValueError, match=r"^research tier must be 1, 2, 3, sonnet, sonnet-high, opus or haiku$"):
        fr.launch("research", tier, CFG)


@pytest.mark.parametrize("tier", ["1", "3", "fast", "sonnet-high"])
def test_implementer_unknown_tier_is_refused(tier):
    with pytest.raises(ValueError, match=r"^implementer tier must be haiku, opus or sonnet$"):
        fr.launch("implementer", tier, CFG)


@pytest.mark.parametrize("tier,agent,model", [(None, "superlite:implementer", "sonnet"), ("sonnet", "superlite:implementer", "sonnet"),
                                              ("haiku", "superlite:implementer-haiku", "haiku"), ("opus", "superlite:implementer", "opus")])
def test_implementer_known_tiers_still_launch(tier, agent, model):
    r = fr.launch("implementer", tier, CFG)
    assert (r["agent"], r["model"]) == (agent, model) and r["argv"][2:4] == ["--model", model]


def test_fleet_md_research_row_names_the_tiers():
    row = next(x for x in (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8").splitlines() if x.startswith("| `research` |"))
    for part in ("`--tier 1|sonnet`", "`2|sonnet-high`", "`3|opus`", "`haiku`", "exits 2"):
        assert part.replace("|", "\\|") in row, part


def test_spawn_research_bad_tier_exits_2_before_any_pane(world, capsys):
    fleet.main(["on"])
    b = world.sd / "briefs" / "R1.md"; b.parent.mkdir(exist_ok=True); b.write_text("Answer the question.\n")
    n = len(world.fh.calls)
    capsys.readouterr()
    assert fleet.main(["spawn", "--role", "research", "--tier", "3x", "--brief", str(b), "--plan", str(world.sd)]) == 2
    assert capsys.readouterr().err == "error: research tier must be 1, 2, 3, sonnet, sonnet-high, opus or haiku\n"
    assert len(world.fh.calls) == n
    assert json.loads((world.sd / "fleet.json").read_text()).get("workers", {}) == {}
