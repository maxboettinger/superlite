"""backlog wait's status re-prompt to a planning lead names `DONE planned: <plan path>` (#732)."""
import pytest

from test_backlog_run import br, bk, run, running  # noqa: F401


def texts(bk):
    return [c[1][3] for c in bk.calls if c[0] == "text"]


def test_reprompt_plan_names_done_planned():
    assert br.REPROMPT_PLAN == br.REPROMPT.replace("Status: DONE, ", "Status: DONE planned: <plan path>, DONE, ", 1)
    assert "end your turn only with Status: DONE planned: <plan path>, DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT or BLOCKED" in br.REPROMPT_PLAN
    assert br.REPROMPT.count("Status: DONE, ") == 1 and "planned" not in br.REPROMPT


@pytest.mark.parametrize("phase,want", [("plan", "REPROMPT_PLAN"), ("build", "REPROMPT"), ("single", "REPROMPT"), (None, "REPROMPT")])
def test_wait_reprompts_with_the_phase_text(bk, capsys, phase, want):
    running(bk, **({"phase": phase} if phase else {}))
    bk.stops["W1"] = {"t": 2000, "last": "PONG"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert texts(bk) == [getattr(br, want)]


def test_planning_lead_second_miss_still_parks(bk, capsys):
    running(bk, phase="plan", reprompted=True)
    bk.stops["W1"] = {"t": 2000, "last": "PONG"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: no status in stop text: PONG\n")
    assert texts(bk) == []
