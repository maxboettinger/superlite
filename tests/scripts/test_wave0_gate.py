import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import next_tasks  # noqa: E402


def setup(tmp_path, wave0=None, ledger="", stable=None):
    sd = tmp_path / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    if wave0 is not None:
        (sd / "briefs" / "wave0.json").write_text(wave0 if isinstance(wave0, str) else json.dumps(wave0))
    (sd / "progress.md").write_text(ledger)
    if stable is not None:
        (sd / "stable.json").write_text(json.dumps({"stable": stable}))
    (tmp_path / "plan.md").write_text("# plan\n")
    return sd


W = {"id": "T0", "wait": ["T1", "T3"]}


def test_waiting_until_t0_commit(tmp_path):
    assert next_tasks.wave0_waiting(setup(tmp_path, W)) == {"T1", "T3"}


def test_commit_line_releases(tmp_path):
    sd = setup(tmp_path, W, "- commit T0 abcdef1234 skeleton\n")
    assert next_tasks.wave0_waiting(sd) == set()


def test_skip_ruling_releases(tmp_path):
    sd = setup(tmp_path, W, "- Ruling: skip T0 - not needed\n")
    assert next_tasks.wave0_waiting(sd) == set()


def test_missing_or_bad_wave0_json_waits_nothing(tmp_path):
    assert next_tasks.wave0_waiting(setup(tmp_path)) == set()
    sd = tmp_path / ".superlite"
    (sd / "briefs" / "wave0.json").write_text("{not json")
    assert next_tasks.wave0_waiting(sd) == set()
    (sd / "briefs" / "wave0.json").write_text(json.dumps({"id": "T0", "wait": "T1"}))
    assert next_tasks.wave0_waiting(sd) == set()


def test_stable_filter_subtracts_waiting(tmp_path):
    sd = setup(tmp_path, W, stable=["T1", "T2", "T3"])
    plan = str(tmp_path / "plan.md")
    assert next_tasks.stable_filter(plan) == {"T2"}
    (sd / "progress.md").write_text("- commit T0 abcdef1234 x\n")
    assert next_tasks.stable_filter(plan) == {"T1", "T2", "T3"}


def test_other_id_released_by_its_own_commit(tmp_path):
    sd = setup(tmp_path, {"id": "T1", "wait": ["T2"]}, "- commit T0 abcdef1234 x\n")
    assert next_tasks.wave0_waiting(sd) == {"T2"}
    (sd / "progress.md").write_text("- commit T1 abcdef1234 x\n")
    assert next_tasks.wave0_waiting(sd) == set()


def test_skip_ruling_of_longer_id_does_not_release(tmp_path):
    sd = setup(tmp_path, W, "- Ruling: skip T01 - other\n")
    assert next_tasks.wave0_waiting(sd) == {"T1", "T3"}
