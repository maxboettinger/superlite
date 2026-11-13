# tests/scripts/test_fleet_roles.py
import sys
import pytest
from test_plan_tools import ROOT, SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402

CFG = routing.load_cfg()
TAIL = ["--disallowedTools", "AskUserQuestion"]

def test_implementer_keeps_model_and_prime_and_gets_effort():
    assert fr.launch("implementer", "sonnet", CFG) == {
        "role": "implementer", "agent": "superlite:implementer", "model": "sonnet", "effort": "medium",
        "argv": ["--agent", "superlite:implementer", "--model", "sonnet", "--effort", "medium"] + TAIL,
        "prime": True, "pool": True, "one_turn": False}
    h = fr.launch("implementer", "haiku", CFG)
    assert h["argv"][:6] == ["--agent", "superlite:implementer-haiku", "--model", "haiku", "--effort", "high"]
    assert fr.launch("implementer", None, CFG)["model"] == "sonnet"

@pytest.mark.parametrize("tier,agent,model,effort", [
    (None, "superlite:fixer-sonnet", "sonnet", "medium"), ("1", "superlite:fixer-sonnet", "sonnet", "medium"),
    ("2", "superlite:fixer-sonnet-high", "sonnet", "high"), ("sonnet-high", "superlite:fixer-sonnet-high", "sonnet", "high"),
    ("3", "superlite:fixer-opus", "opus", "high"), ("opus", "superlite:fixer-opus", "opus", "high")])
def test_fixer_tiers_follow_fixing_md(tier, agent, model, effort):
    r = fr.launch("fixer", tier, CFG)
    assert (r["agent"], r["model"], r["effort"]) == (agent, model, effort)
    assert r["argv"] == ["--agent", agent, "--effort", effort] + TAIL and not r["prime"] and not r["pool"] and r["one_turn"]

def test_reviewers_take_frontmatter_model_without_model_flag():
    f = fr.launch("final-reviewer", None, CFG)
    assert (f["agent"], f["model"], f["effort"]) == ("superlite:final-reviewer", "opus", "high") and "--model" not in f["argv"]
    p = fr.launch("package-reviewer", None, CFG)
    assert p["argv"] == ["--agent", "superlite:package-reviewer", "--effort", "medium"] + TAIL and p["model"] == "sonnet"

def test_research_runs_the_read_only_researcher():
    r = fr.launch("research", None, CFG)
    assert r["argv"] == ["--agent", "superlite:researcher", "--model", "sonnet", "--effort", "low"] + TAIL + ["Edit", "Write", "NotebookEdit", "Bash"] and r["model"] == "sonnet" and r["one_turn"]
    s = fr.launch("research", "sonnet", CFG)
    assert s["argv"][:4] == ["--agent", "superlite:researcher", "--model", "sonnet"] and s["model"] == "sonnet"

@pytest.mark.parametrize("role,tier", [("lead", None), ("fixer", "haiku"), ("fixer", "4"), ("final-reviewer", "opus"), ("package-reviewer", "sonnet")])
def test_bad_role_or_tier_is_value_error(role, tier):
    with pytest.raises(ValueError):
        fr.launch(role, tier, CFG)

def test_unknown_role_message_lists_the_roles():
    with pytest.raises(ValueError, match="unknown role lead; use implementer, fixer, package-reviewer, final-reviewer, research"):
        fr.launch("lead", None, CFG)

def test_env_names_role_and_turns_off_prompt_suggestions():
    assert fr.env("fixer") == {"SUPERLITE_FLEET_ROLE": "fixer", "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0"}
    assert fr.env("implementer")["SUPERLITE_FLEET_ROLE"] == "implementer"

def test_missing_agent_file_drops_effort(tmp_path):
    r = fr.launch("final-reviewer", None, CFG, agents_dir=tmp_path)
    assert r["argv"] == ["--agent", "superlite:final-reviewer"] + TAIL and r["effort"] is None and r["model"] is None

def test_researcher_agent_is_read_only():
    text = (ROOT / "agents" / "researcher.md").read_text(encoding="utf-8")
    fm = text.split("---")[1]
    assert "name: researcher" in fm and "model: haiku" in fm and "effort: low" in fm and "tools: Read, Grep, Glob\n" in fm
    assert "absolute" in text and "no shell" in text and "$SL" not in text


# --- #669: brief-only implementer, tier text ---
def test_launch_brief_only_implementer():
    assert fr.launch("implementer", None, CFG, brief=True) == {
        "role": "implementer", "agent": "superlite:implementer", "model": "sonnet", "effort": "medium",
        "argv": ["--agent", "superlite:implementer", "--model", "sonnet", "--effort", "medium"] + TAIL,
        "prime": False, "pool": False, "one_turn": True}

def test_launch_brief_ignored_for_other_roles():
    for role, tier in (("fixer", "1"), ("research", None), ("package-reviewer", None)):
        assert fr.launch(role, tier, CFG, brief=True) == fr.launch(role, tier, CFG)

@pytest.mark.parametrize("role", ["package-reviewer", "final-reviewer", "checker"])
def test_tier_refusal_names_tier_roles(role):
    with pytest.raises(ValueError, match=r"^%s takes no --tier \(its agent file sets the model\); --tier works for implementer, fixer, research and writer$" % role):
        fr.launch(role, "opus", CFG)

def test_brief_only_text():
    assert fr.BRIEF_ONLY.startswith("No prime and no plan run: this brief is your whole task")
    assert "plain `git add <files>` and `git commit`" in fr.BRIEF_ONLY


# --- #669: spawn --role implementer --brief without a prime ---
import json  # noqa: E402
from test_fleet import REAL, fleet, world  # noqa: E402,F401

_skip_real = pytest.mark.skipif(REAL, reason="calls are read from the in-process fake")

def _brief(world):
    f = world.proj / "b.md"; f.write_text("do it\n"); return f

def _prompts(world):
    return [c[2] for c in world.fh.calls if c[0] == "prompt"]

@_skip_real
def test_spawn_brief_only_implementer_without_prime(world, monkeypatch):
    import fleet_io; monkeypatch.setattr(fleet_io, "hc", world.fh)
    fleet.main(["on"]); (world.sd / "prime.md").unlink(); F = _brief(world)
    assert fleet.main(["spawn", "--role", "implementer", "--brief", str(F), "--plan", str(world.sd)]) == 0
    ps = _prompts(world)
    assert not any("prime.md" in p for p in ps)
    hits = [p for p in ps if p.startswith(fr.BRIEF_ONLY)]
    assert len(hits) == 1 and f"Read {F.resolve()}" in hits[0]
    pj = world.sd / "pool.json"
    assert not pj.exists() or json.loads(pj.read_text())["agents"] == []
    rec = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert rec["one_turn"] is True and rec["brief_only"] is True

@_skip_real
def test_spawn_implementer_with_prime_and_brief_keeps_prime(world, monkeypatch):
    import fleet_io; monkeypatch.setattr(fleet_io, "hc", world.fh)
    fleet.main(["on"]); F = _brief(world)
    assert fleet.main(["spawn", "--role", "implementer", "--brief", str(F), "--plan", str(world.sd)]) == 0
    ps = _prompts(world)
    assert "prime.md" in ps[0]
    assert not any(fr.BRIEF_ONLY in p for p in ps)
    assert json.loads((world.sd / "pool.json").read_text())["agents"][0]["id"] == "W1"

@_skip_real
def test_spawn_implementer_no_prime_no_brief_blocked(world, capsys):
    fleet.main(["on"]); (world.sd / "prime.md").unlink(); world.fh.calls.clear()
    with pytest.raises(SystemExit) as e:
        fleet.main(["spawn", "--role", "implementer", "--plan", str(world.sd)])
    assert e.value.code == 3
    assert capsys.readouterr().out.strip() == f"BLOCKED: no {world.sd.resolve()}/prime.md; run build_prime --plan PLAN first, or pass --brief FILE for a brief-only task outside a plan run"
    assert "start_agent" not in [c[0] for c in world.fh.calls]
