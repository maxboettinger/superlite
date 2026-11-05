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
    assert r["argv"] == ["--agent", "superlite:researcher", "--effort", "low"] + TAIL + ["Edit", "Write", "NotebookEdit", "Bash"] and r["model"] == "haiku" and r["one_turn"]
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
