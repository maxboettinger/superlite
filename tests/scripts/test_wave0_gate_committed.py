import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run
from test_wave0 import PY, plan

sys.path.insert(0, str(SCRIPTS))
import next_tasks  # noqa: E402


def setup(tmp_path, wave0, stable=None):
    sd = tmp_path / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    (sd / "briefs" / "wave0.json").write_text(json.dumps(wave0))
    (sd / "progress.md").write_text("")
    if stable is not None:
        (sd / "stable.json").write_text(json.dumps({"stable": stable}))
    (tmp_path / "plan.md").write_text("# plan\n")
    return sd


def test_committed_t0_releases_wait(tmp_path):
    sd = setup(tmp_path, {"id": "T0", "wait": ["T1", "T3"]})
    assert next_tasks.wave0_waiting(sd, {"T0"}) == set()
    assert next_tasks.wave0_waiting(sd, {"T2"}) == {"T1", "T3"}
    assert next_tasks.wave0_waiting(sd) == {"T1", "T3"}


def test_committed_other_id(tmp_path):
    sd = setup(tmp_path, {"id": "T1", "wait": ["T2"]})
    assert next_tasks.wave0_waiting(sd, ["T0"]) == {"T2"}
    assert next_tasks.wave0_waiting(sd, ["T1"]) == set()


def test_stable_filter_committed(tmp_path):
    setup(tmp_path, {"id": "T0", "wait": ["T1", "T3"]}, stable=["T1", "T2", "T3"])
    plan_path = str(tmp_path / "plan.md")
    assert next_tasks.stable_filter(plan_path, {"T0"}) == {"T1", "T2", "T3"}
    assert next_tasks.stable_filter(plan_path) == {"T2"}


def test_cli_committed_t0_offers_stub_owner(tmp_path):
    sd = setup(tmp_path, {"id": "T0", "wait": ["T1"]}, stable=["T1", "T2"])
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    script = SCRIPTS / "next_tasks.py"
    assert run(script, "--plan", p, "--committed", "T0", cwd=tmp_path).out.split() == ["T1"]
    assert run(script, "--plan", p, cwd=tmp_path).out.strip() == ""
