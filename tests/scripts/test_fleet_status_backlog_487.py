import sys
from pathlib import Path
import pytest
from backlog_fixtures import batch
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402
import fleet  # noqa: E402
import fleet_lead as fl  # noqa: E402


@pytest.fixture
def mroot(tmp_path, monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    root = tmp_path / "m"; (root / ".superlite").mkdir(parents=True)
    monkeypatch.setattr(bs, "main_root", lambda cwd: root)
    return root


def put(root, *bs_):
    bs.update(bs.path(root), lambda d: d.update({"batches": list(bs_)}))


def test_backlog_hint_examples(mroot, tmp_path, monkeypatch):
    sd = tmp_path / "run"
    assert fl.backlog_hint(sd, mroot) is None
    put(mroot, batch("B7", ["a"], "running", lead="W3"), batch("B8", ["b"], "shipped", lead="W2"), batch("B9", ["c"], "needs_decision", lead="W4"))
    assert fl.backlog_hint(sd, mroot) == f"backlog: 2 leads run in {mroot}/.superlite (B7 W3, B9 W4); sl backlog status lists them, sl backlog tell B --text T messages one"
    assert fl.backlog_hint(mroot / ".superlite", mroot) is None
    put(mroot, batch("B7", ["a"], "running", lead="W3"))
    assert fl.backlog_hint(sd, mroot) == f"backlog: 1 lead runs in {mroot}/.superlite (B7 W3); sl backlog status lists it, sl backlog tell B --text T messages it"
    put(mroot, batch("B8", ["b"], "shipped", lead="W2"), batch("B9", ["c"], "running"))
    assert fl.backlog_hint(sd, mroot) is None
    put(mroot, batch("B7", ["a"], "running", lead="W3"))
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    assert fl.backlog_hint(sd, mroot) is None
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER")
    def boom(cwd): raise RuntimeError("no")
    monkeypatch.setattr(bs, "main_root", boom)
    assert fl.backlog_hint(sd, mroot) is None


def test_no_backlog_json(mroot, tmp_path):
    assert fl.backlog_hint(tmp_path / "run", mroot) is None


@pytest.mark.parametrize("hint,out", [("backlog: x", "fleet: off\nbacklog: x\n"), (None, "fleet: off\n")])
def test_status_prints_the_hint(tmp_path, monkeypatch, capsys, hint, out):
    monkeypatch.setattr(fleet, "_sd", lambda a: tmp_path)
    monkeypatch.setattr(fleet.fs, "is_on", lambda sd: False)
    monkeypatch.setattr(fl, "backlog_hint", lambda sd, cwd: hint)
    assert fleet.main(["status"]) == 0
    assert capsys.readouterr().out == out


def test_status_with_plan_prints_no_hint(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fleet, "_sd", lambda a: tmp_path)
    monkeypatch.setattr(fleet.fs, "is_on", lambda sd: False)
    monkeypatch.setattr(fl, "backlog_hint", lambda sd, cwd: "backlog: x")
    assert fleet.main(["status", "--plan", str(tmp_path / "docs" / "new-plan.md")]) == 0
    assert capsys.readouterr().out == "fleet: off\n"
