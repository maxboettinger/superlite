"""#603 item 1 (B146): the coordinator guard's fix line says where a hand-written fixer brief goes."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_block_coordinator_edits import proj, run  # noqa: E402,F401

sys.path.insert(0, str(HERE.parents[1] / "skills" / "subagent-driven-development" / "scripts"))
import guard_judge as gj  # noqa: E402

FIX = ("- Fix: give a fixer a finding id F-<Tn>-<n>, tiered per skills/subagent-driven-development/fixing.md: known cause, "
       "one module -> fixer-sonnet; cross-module -> fixer-sonnet-high; unknown cause -> fixer-opus. A brief you write by "
       "hand goes to .superlite/briefs/fix-<id>.md (`sl findings route` writes them for you); .superlite/fixes/<id>.md "
       "holds only the note the fixer writes itself.")


def test_hook_fix_line(proj):  # noqa: F811
    r = run(proj, "Edit", {"file_path": str(proj / "src" / "app.py")})
    assert r.returncode == 2
    assert [ln for ln in r.stderr.splitlines() if ln.startswith("- Fix:")] == [FIX]


def test_judge_fix_line_matches_the_hook():
    assert [ln for ln in gj.MESSAGES["code"] if ln.startswith("- Fix:")] == [FIX]
