"""metrics.py gives each task its own work (#93): handover messages, batches, build order, reviewers, polls.

The coordinator messages copy real 2026-11-03 shapes: a reused implementer told `T1 recorded, thanks. Next: Task T2 …`,
batches headed `## Tasks T11 …, then T8 … (in this order)` or `## Batch: T4 …, then T5 …` answered by one report with a
status per task, a fresh re-dispatch whose agent id sorts before the first agent's, package reviewers, relevance polls."""
from __future__ import annotations

import json

import pytest

from test_metrics_handback import COORD, ENFORCE, SONNET, Transcript
from test_plan_tools import run
from test_metrics_handback import METRICS

PRIME = "Read /work/app/.superlite/prime.md, then reply READY"
IMPL = "superlite:implementer"


class At(Transcript):
    """A transcript whose first entry is `offset_s` seconds after 16:00, so two agents can run one after the other."""

    def __init__(self, model, offset_s=0):
        super().__init__(model)
        self.offset = offset_s

    def _ts(self):
        s = self.offset + len(self.lines) * 5
        return f"2026-11-03T{16 + s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}.000Z"


def records(tmp_path, agents):
    """agents: (agent id, type, launch desc, transcript path) in launch order -> {task: row}."""
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    t0, rows = 1_793_724_780_000, []
    for i, (aid, typ, desc, path) in enumerate(agents):
        rows += [{"ev": "launch", "t": t0 + i, "agent_id": aid, "type": typ, "model": SONNET, "desc": desc},
                 {"ev": "stop", "t": t0 + 900_000 + i, "agent_id": aid, "type": typ, "transcript": str(path), "last": ""}]
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cp = run(METRICS, "--dir", sl, "--json", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return {r["task"]: r for r in json.loads(cp.out)}


def test_a_message_that_records_one_task_and_hands_over_the_next_opens_the_next(tmp_path):
    path = (At(SONNET).user(PRIME).user(ENFORCE).handback("READY")
            .user(COORD + "Task T1 value format and chart tokens.\n\nSUPERLITE=/work/superlite")
            .tool("Bash").handback("Status: DONE\n\nFiles changed:\n- Sources/Theme/ThemeChart.swift")
            .user(COORD + "T1 recorded, thanks. Next: Task T2 bar chart model options.\n\nSUPERLITE=/work/superlite")
            .tool("Bash").handback("Status: DONE_WITH_CONCERNS\n\nFiles changed:\n- Sources/Models/BarChartModel.swift\n"
                                   "Concern: the scale clamps at zero.")
            .user(COORD + "T2 recorded. Next: Task T3 bar chart view options.\n\nSUPERLITE=/work/superlite")
            .tool("Bash").handback("Status: BLOCKED\n\nThe build fails in another owner's file.")
            .write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T1", path)])
    assert {t: r[t]["status"] for t in ("T1", "T2", "T3")} == {"T1": "DONE", "T2": "DONE_WITH_CONCERNS", "T3": "BLOCKED"}
    assert [r[t]["dispatches"] for t in ("T1", "T2", "T3")] == [1, 1, 1]


def test_a_dependency_named_in_a_single_task_heading_is_not_a_batch(tmp_path):
    """Guard for the batch rule: only `Tasks`/`Batch` headings hand over every id they name."""
    path = (At(SONNET).user(PRIME).handback("READY")
            .user(COORD + "Task T5 line chart view (consumes T4's LineChartScales).\n\nSUPERLITE=/work/superlite")
            .tool("Edit").handback("Status: DONE").write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T5", path)])
    assert set(r) == {"T5"} and r["T5"]["status"] == "DONE"


def test_a_task_named_mid_sentence_in_a_retry_is_not_handed_over(tmp_path):
    """A cue counts only at the start of a line or sentence: `… the file of task T9` keeps the retry on T6."""
    path = (At(SONNET).user(PRIME).handback("READY").user(COORD + "Task T6 area keywords.")
            .tool("Bash").handback("Status: BLOCKED\nThe build fails in another owner's file.")
            .user(COORD + "T6 retry: the blocker was the half-written file of task T9. Continue T6 exactly as specified.")
            .tool("Edit").handback("Status: DONE_WITH_CONCERNS\nConcern: the patterns compile on each call.")
            .write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T6", path)])
    assert set(r) == {"T6"}
    assert (r["T6"]["status"], r["T6"]["dispatches"], r["T6"]["first_time_pass"]) == ("DONE_WITH_CONCERNS", 1, False)


def batch_agent(path, heading, report):
    return (At(SONNET).user(PRIME).user(ENFORCE).handback("READY")
            .user(COORD + heading + "\nSUPERLITE=/work/superlite\nPLAN=/work/app/docs/plans/plan.md")
            .tool("Read").tool("Edit").tool("Bash").tool("Edit").tool("Bash").text("Both suites pass.")
            .handback(report).write(path))


BATCHES = [
    ("## Tasks T11 check-ins model, then T8 daily card parity (in this order)",
     "T11: DONE\nFiles: Sources/WidgetsMood/CheckInsModel.swift\nTest: 7 CheckInsModelTests pass.\n\n"
     "T8: DONE_WITH_CONCERNS\nFiles: Sources/WidgetsMood/DailyCard.swift\nConcern: the card reads the store twice.",
     {"T11": "DONE", "T8": "DONE_WITH_CONCERNS"}),
    ("## Batch: T4 line chart scales, then T5 line chart view and legend",
     "T4: DONE. T5: DONE_WITH_CONCERNS.\n\nFiles changed:\n- Sources/Models/LineChartScales.swift\n- Sources/LineChart.swift",
     {"T4": "DONE", "T5": "DONE_WITH_CONCERNS"}),
    ("## Tasks T13 mood trend model, then T12 mood heat model (in this order)",
     "Status: DONE\n\nBoth suites pass, with no failures in the output.",
     {"T13": "DONE", "T12": "DONE"}),
]


@pytest.mark.parametrize("heading,report,want", BATCHES, ids=["sections", "one-line", "overall"])
def test_a_batch_gives_each_task_its_status_and_an_even_share_in_order(tmp_path, heading, report, want):
    first, second = list(want)
    (tmp_path / "control").mkdir()
    alone = batch_agent(tmp_path / "control" / "c1.jsonl", f"Task {first} alone.", report)
    whole = records(tmp_path / "control", [("c1", IMPL, "Implementer", alone)])[first]  # no Tn: the prime is no task's
    path = batch_agent(tmp_path / "a1.jsonl", heading, report)
    r = records(tmp_path, [("a1", IMPL, "Implementer", path)])
    assert {t: r[t]["status"] for t in want} == want
    a, b = r[first], r[second]
    for k in ("in", "out", "cache_read", "cache_write"):
        assert a["tokens"][k] + b["tokens"][k] == whole["tokens"][k]
        assert abs(a["tokens"][k] - b["tokens"][k]) <= 1
    assert a["cost_usd"] + b["cost_usd"] == pytest.approx(whole["cost_usd"], abs=1e-5)
    assert a["tool_calls"] + b["tool_calls"] == whole["tool_calls"]
    assert a["duration_s"] + b["duration_s"] == pytest.approx(whole["duration_s"], abs=0.2)
    assert a["end_s"] <= b["start_s"]  # in the heading's order


def test_the_final_build_is_the_latest_by_time_not_by_agent_id(tmp_path):
    early = (At(SONNET, 0).user(PRIME).handback("READY").user(COORD + "Task T5 line chart view.")
             .tool("Bash").handback("Status: BLOCKED\nThe red step does not compile: T4's file is half-written.")
             .write(tmp_path / "b9.jsonl"))
    late = (At(SONNET, 1200).user(PRIME).handback("READY").user(COORD + "Task T5 line chart view (retry after T4).")
            .tool("Bash").handback("Status: DONE\nTest: 12 LineChartTests pass.").write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("b9", IMPL, "Implementer for T5", early), ("a1", IMPL, "Implementer for T5 (retry)", late)])
    assert (r["T5"]["status"], r["T5"]["agent"], r["T5"]["dispatches"]) == ("DONE", "a1", 2)
    assert r["T5"]["first_time_pass"] is False  # the BLOCKED report came first


@pytest.mark.parametrize("desc", ["Package review T1", "Package review + fixes T1"])
def test_a_package_reviewer_is_neither_a_build_nor_rework(tmp_path, desc):
    impl = (At(SONNET, 0).user(PRIME).handback("READY").user(COORD + "Task T1 value format and chart tokens.")
            .tool("Edit").handback("Status: DONE\nFiles changed:\n- Sources/Theme/ThemeChart.swift").write(tmp_path / "a1.jsonl"))
    review = (At(SONNET, 1200).user("Package review: shared layers of the build (tasks T1).\n\nsl: /work/sl\nPLAN: /work/plan.md")
              .tool("Read").tool("Edit").handback("Verdict: approved after one fix.\nF-T1-1 fixed with a regression test.")
              .write(tmp_path / "r1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T1", impl), ("r1", "superlite:package-reviewer", desc, review)])
    row = r["T1"]
    assert (row["status"], row["dispatches"], row["rework_dispatches"], row["first_time_pass"]) == ("DONE", 1, 0, True)
    assert row["agent"] == "a1"


@pytest.mark.parametrize("desc", ["Fix package reviewer finding F-T1-1", "Final review fixes T1"])
def test_a_fixer_whose_description_names_a_review_is_still_rework(tmp_path, desc):
    """Final review: only a `…reviewer` type or a description that starts `Package review`/`Final review` is a reviewer."""
    impl = (At(SONNET, 0).user(PRIME).handback("READY").user(COORD + "Task T1 value format and chart tokens.")
            .tool("Edit").handback("Status: DONE").write(tmp_path / "a1.jsonl"))
    fix = (At(SONNET, 1200).user("Fix-only brief. Finding F-T1-1, owning task T1.\nsl: /work/sl")
           .tool("Edit").handback("Status: DONE\nF-T1-1 fixed with a regression test.").write(tmp_path / "f1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T1", impl), ("f1", "superlite:fixer-sonnet", desc, fix)])
    assert (r["T1"]["rework_dispatches"], r["T1"]["first_time_pass"]) == (1, False)


def test_a_lower_case_done_in_a_batch_report_is_no_status(tmp_path):
    """Final review: `T5 could not be done` must not read as T5's status; status tokens are upper case, as in LEAD."""
    path = batch_agent(tmp_path / "a1.jsonl", "## Tasks T4 line chart scales, then T5 line chart view (in this order)",
                       "Status: BLOCKED\nT5 could not be done: T4's file is half-written.")
    r = records(tmp_path, [("a1", IMPL, "Implementer", path)])
    assert (r["T4"]["status"], r["T5"]["status"]) == ("BLOCKED", "BLOCKED")


@pytest.mark.parametrize("heading", ["## Tasks T11 check-ins model, then T8 daily card parity (consumes T4's store, in this order)",
                                     "## Tasks T11 check-ins model, then T8 daily card on T4's store"])
def test_a_dependency_in_a_batch_heading_is_not_a_batch_member(tmp_path, heading):
    path = batch_agent(tmp_path / "a1.jsonl", heading, "T11: DONE\nT8: DONE")
    r = records(tmp_path, [("a1", IMPL, "Implementer", path)])
    assert set(r) == {"T11", "T8"}


def test_a_hinted_prime_joins_the_batch_it_precedes(tmp_path):
    """Final review: a launch description naming T11 puts the prime on T11; the batch must not give T11 a second build."""
    path = batch_agent(tmp_path / "a1.jsonl", BATCHES[0][0], BATCHES[0][1])
    r = records(tmp_path, [("a1", IMPL, "Implementer for T11", path)])
    assert (r["T11"]["dispatches"], r["T8"]["dispatches"]) == (1, 1)
    assert abs(r["T11"]["tokens"]["in"] - r["T8"]["tokens"]["in"]) <= 1


def test_an_acknowledgement_after_a_poll_resumes_the_task(tmp_path):
    """Final review: `T1 recorded` after a poll is no second T1 build (a build with no report reads as status None)."""
    path = (At(SONNET).user(PRIME).handback("READY").user(COORD + "Task T1 value format and chart tokens.")
            .tool("Edit").handback("Status: DONE")
            .user(COORD + "Relevance 0-10 for T7 (files, consumes)? Reply `score: N - reason`")
            .handback("score: 2 - T7 is in another module")
            .user(COORD + "T1 recorded, thanks.").text("Noted.").write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T1", path)])
    assert (set(r), r["T1"]["dispatches"], r["T1"]["status"]) == ({"T1"}, 1, "DONE")


def test_a_relevance_poll_opens_no_task(tmp_path):
    path = (At(SONNET).user(PRIME).handback("READY").user(COORD + "Task T1 value format and chart tokens.")
            .tool("Edit").handback("Status: DONE")
            .user(COORD + "Relevance 0-10 for T7 (files, consumes)? Reply `score: N - reason`")
            .handback("score: 2 - T7 is in another module").write(tmp_path / "a1.jsonl"))
    r = records(tmp_path, [("a1", IMPL, "Implementer for T1", path)])
    assert set(r) == {"T1"} and r["T1"]["status"] == "DONE"
