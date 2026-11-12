"""#600: the checker fleet role runs superlite:checker as a one-turn brief worker; it takes no --tier."""
import sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402

CFG = routing.load_cfg()
TAIL = ["--disallowedTools", "AskUserQuestion"]


def test_checker_launch_reads_its_agent_file(tmp_path):
    (tmp_path / "checker.md").write_text("---\nname: checker\nmodel: sonnet\neffort: high\n---\nbody\n", encoding="utf-8")
    r = fr.launch("checker", None, CFG, agents_dir=tmp_path)
    assert r == {"role": "checker", "agent": "superlite:checker", "model": "sonnet", "effort": "high",
                 "argv": ["--agent", "superlite:checker", "--effort", "high"] + TAIL,
                 "prime": False, "pool": False, "one_turn": True}


@pytest.mark.parametrize("tier", ["sonnet", "opus", "1"])
def test_checker_takes_no_tier(tier):
    with pytest.raises(ValueError, match="checker takes no --tier"):
        fr.launch("checker", tier, CFG)


def test_unknown_role_lists_checker():
    assert fr.ROLES[-1] == "checker"
    with pytest.raises(ValueError, match="^unknown role lead; use implementer, fixer, package-reviewer, final-reviewer, research, checker$"):
        fr.launch("lead", None, CFG)


def test_checker_env_names_the_role():
    assert fr.env("checker")["SUPERLITE_FLEET_ROLE"] == "checker"
