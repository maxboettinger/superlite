"""The fixture copy keeps fixture plans away from the checkout's live .superlite (#19)."""
import re
import subprocess
import sys
from pathlib import Path

from _fixtures import FIXTURES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402


def test_fixture_copy_is_outside_git():
    r = subprocess.run(["git", "-C", str(FIXTURES), "rev-parse"], capture_output=True)
    assert r.returncode != 0
    assert ROOT.resolve() not in FIXTURES.resolve().parents


def test_fixture_plan_resolves_to_copy():
    plan = FIXTURES / "run_plan" / "plan.md"
    assert state.plan_dir(plan) == FIXTURES / "run_plan" / ".superlite"


def test_no_module_reads_live_fixtures():
    pat = re.compile(r'/\s*"fixtures"')
    for f in HERE.glob("test_*.py"):
        if f.name == Path(__file__).name:
            continue
        for n, line in enumerate(f.read_text().splitlines(), 1):
            assert not pat.search(line), f"{f.name}:{n} builds a live fixtures path"


def test_fake_sl_is_run_through_bash_only():
    src = (SCRIPTS / "next_tasks.py").read_text()
    assert 'os.environ.get("SUPERLITE_BASH") or "bash", launcher' in src


def test_next_tasks_ignores_live_stable_json():
    from test_run_scripts import ready
    assert ready() == ["T2", "T5", "T4", "T1"]
