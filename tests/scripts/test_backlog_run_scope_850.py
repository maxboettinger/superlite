import pytest
from test_backlog_run import bk, put, get, run, running, bs  # noqa: F401


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


def test_shipped_line_counts_scope(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", followups=["file docs"], scope=["dropped CSV export", "added a flag"])
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    s = bk.sd / "backlog" / "B1.md"
    assert run(capsys, "wait", "--timeout", "0") == (0, f"B1 shipped PR #201 1.5.8 summary={s} followups=1 scope=2\nB1 follow-up: file docs\n")


def test_shipped_line_scope_after_unverified(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", unverified=["app check (#3)"], scope=["x"])
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    s = bk.sd / "backlog" / "B1.md"
    first = run(capsys, "wait", "--timeout", "0")[1].splitlines()[0]
    assert first.endswith(f"summary={s} unverified=1 scope=1")


def test_shipped_line_without_scope(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", scope=[])
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    assert run(capsys, "wait", "--timeout", "0") == (0, f"B1 shipped PR #201 1.5.8 summary={bk.sd / 'backlog' / 'B1.md'}\n")
