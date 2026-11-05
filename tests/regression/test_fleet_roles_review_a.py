# tests/regression/test_fleet_roles_review_a.py
import json, sys
import pytest
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
from test_guard_fleet_agents import fleet, guard  # noqa: F401,E402
from test_fleet_hooks import sd  # noqa: F401,E402
from test_plan_tools import SCRIPTS, make_plan  # noqa: E402
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402

@pytest.mark.parametrize("name", ["fixer-opus", "Superlite:Fixer-Opus", "final-reviewer", "implementer", "researcher"])
def test_guard_blocks_bare_and_cased_role_names(sd, name):
    fleet(sd)
    assert guard(sd, name).returncode == 2

@pytest.mark.parametrize("name", ["other:fixer-opus", "my-implementer", "Explore"])
def test_guard_lets_other_names_pass(sd, name):
    fleet(sd)
    assert guard(sd, name).returncode == 0

def test_findings_directory_and_glob_owns_are_owned(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; sd.mkdir(parents=True)
    plan = make_plan(root, [{"id": "T1", "owns": "src/pkg/, tests/**/*.py"}, {"id": "T2", "owns": "src/z.py"}])
    rp = sd / "r.json"
    rp.write_text(json.dumps({"label": "FR1", "findings": [
        {"file": "src/pkg/a.py", "line": 1, "problem": "p", "fix": "x", "tier": 1},
        {"file": "tests/u/test_a.py", "line": 2, "problem": "q", "fix": "x", "tier": 1}]}))
    lines = findings.route(sd, plan, [str(rp)], "/sl/sl")
    assert len(lines) == 1 and lines[0].endswith("task=T1")
    assert "--claim" not in (sd / "briefs" / "fix-F-T1-1.md").read_text()
