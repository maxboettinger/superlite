"""#606: review briefs flag a task whose report shows no red run and list the plan lines that name its types."""
import json
import os
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402
import plan_tools as pt  # noqa: E402

FENCE = "```"
PLAN_TEXT = f"""# Plan
**Goal:** x.

| Type | Conforms to | Task |
|---|---|---|
| FooConfig | Codable, Sendable | T1 |
| Other | Equatable | T2 |

{FENCE}mermaid
flowchart LR
  T1[FooConfig]
  T2[loader]
  %% taskgraph
  T1 --> T2
{FENCE}

## Package: core (library)

### T1 config · Complexity 3 · Est. context 30k
**Owns:** Sources/Core/FooConfig.swift, Tests/CoreTests/FooConfigTests.swift
**Produces:** FooConfig.init(retries: Int) -> FooConfig
**Notes:** FooConfig holds retries.

### T2 loader · Complexity 3 · Est. context 30k
**Owns:** Sources/Core/Loader.swift
**Consumes:** FooConfig.init(retries: Int) -> FooConfig (T1)
**Steps:** 1 decode a FooConfig from JSON through its Codable conformance
"""
OWNS = ["Sources/Core/FooConfig.swift", "Tests/CoreTests/FooConfigTests.swift"]
ROW6 = "- plan:6 (table): | FooConfig | Codable, Sendable | T1 |"


@pytest.fixture
def world(tmp_path):
    proj = tmp_path / "proj"
    sd = proj / ".superlite"
    sd.mkdir(parents=True)
    (proj / ".git").mkdir()
    plan = proj / "plan.md"
    plan.write_text(PLAN_TEXT, encoding="utf-8")
    return type("W", (), {"proj": proj, "sd": sd, "plan": str(plan)})


def report(world, name, label, red, role="implementer", age=0):
    d = world.sd / "fleet" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(json.dumps({"status": "DONE", "label": label, "role": role, "red": red}), encoding="utf-8")
    t = 1_700_000_000 - age
    os.utime(p, (t, t))
    return p


def test_red_gap_kinds(world):
    assert io.red_gap(world.sd, "T1", OWNS) is None
    report(world, "T1", "T1", "")
    assert io.red_gap(world.sd, "T1", OWNS) == "its report names no red run"
    report(world, "T1", "T1", "none - no test")
    assert io.red_gap(world.sd, "T1", OWNS) == ("its report says `none - no test`, but it owns test files "
                                                "(Tests/CoreTests/FooConfigTests.swift)")
    assert io.red_gap(world.sd, "T1", OWNS[:1]) is None
    report(world, "T1", "T1", "tests (fast): 3 passed")
    assert io.red_gap(world.sd, "T1", OWNS) == "its red run `tests (fast): 3 passed` names no failing test"
    report(world, "T1", "T1", "tests (fast): 0 passed, 1 failed")
    assert io.red_gap(world.sd, "T1", OWNS) is None


def test_red_gap_reads_batch_labels_and_the_newest_implementer_report(world):
    report(world, "review-T1", "review-T1", "", role="package-reviewer")
    assert io.red_gap(world.sd, "T1", OWNS) is None
    report(world, "T1", "T1", "tests (fast): 0 passed, 1 failed", age=60)
    report(world, "T2", "T2,T1", "", age=0)
    assert io.red_gap(world.sd, "T1", OWNS) == "its report names no red run"
    assert io.red_gap(world.sd, "T2", []) == "its report names no red run"
    (world.sd / "fleet" / "reports" / "T3.json").write_text("{broken", encoding="utf-8")
    assert io.red_gap(world.sd, "T3", []) is None


def test_contract_mentions(world):
    pl = pt.Plan.load(world.plan)
    names, rows, total = io.contract_mentions(pl, "T1")
    assert names == ["FooConfig"]
    assert rows == [(6, "table", "| FooConfig | Codable, Sendable | T1 |"),
                    (26, "T2", "**Consumes:** FooConfig.init(retries: Int) -> FooConfig (T1)"),
                    (27, "T2", "**Steps:** 1 decode a FooConfig from JSON through its Codable conformance")]
    assert total == 3
    assert io.contract_mentions(pl, "T1", limit=1)[1:] == ([(6, "table", "| FooConfig | Codable, Sendable | T1 |")], 3)
    assert io.contract_mentions(pl, "T2") == (["Loader"], [], 0)


def test_review_brief_flags_the_red_run_and_lists_the_contract(world):
    report(world, "T1", "T1", "")
    lines = io.review_brief(world.sd, world.plan, ["T1"], "/sl/sl", "/sl").splitlines()
    i = lines.index("Red runs (task reports):")
    assert lines[i + 1:i + 3] == ["- T1: its report names no red run", io.RED_PROOF]
    j = lines.index("Plan contract outside T1's Produces (other plan lines that name FooConfig; "
                    "the build must fit each line, a mismatch is a finding):")
    assert lines[j + 1:j + 4] == [ROW6, "- plan:26 (T2): **Consumes:** FooConfig.init(retries: Int) -> FooConfig (T1)",
                                  "- plan:27 (T2): **Steps:** 1 decode a FooConfig from JSON through its Codable conformance"]
    assert j < i
    assert [ln for ln in lines if ln.strip()][-1].startswith("Probe adapter:")


def test_review_brief_without_gaps_or_mentions_adds_nothing(world):
    report(world, "T2", "T2", "tests (fast): 0 passed, 1 failed")
    out = io.review_brief(world.sd, world.plan, ["T2"], "/sl/sl", "/sl")
    assert "Red runs" not in out and "Plan contract outside" not in out


def test_contract_rows_over_the_limit_name_the_rest(world, monkeypatch):
    monkeypatch.setattr(io, "CONTRACT_LIMIT", 1)
    lines = io.review_brief(world.sd, world.plan, ["T1"], "/sl/sl", "/sl").splitlines()
    j = [n for n, ln in enumerate(lines) if ln.startswith("Plan contract outside T1")][0]
    assert lines[j + 1:j + 3] == [ROW6, "- (2 more: grep the plan for FooConfig)"]


def test_review_hints_name_a_missing_red_run(world):
    (world.sd / "progress.md").write_text("- commit T1 abc1234 config\n", encoding="utf-8")
    report(world, "T1", "T1", "")
    assert dict(io.review_hints(world.sd, world.plan))["T1"] == ["seam T1↔T2", "no red run"]


def test_red_gap_zero_failed_is_not_a_red_run(world):
    for red in ("tests (fast): 3 passed, 0 failed", "3 passed, 0 errors"):
        report(world, "T1", "T1", red)
        assert io.red_gap(world.sd, "T1", OWNS) == f"its red run `{red}` names no failing test"
    report(world, "T1", "T1", "tests (fast): 1 FAILED test_x")
    assert io.red_gap(world.sd, "T1", OWNS) is None


def test_red_gap_counts_and_fail_words(world):
    for red, gap in (("3 passed, 0 failed", True), ("1 failed, 2 passed", False), ("0 failed, 1 failing", False),
                     ("2 errors", True), ("1 error in collection", True), ("FAIL test_x", False), ("red: test_x Failure", False)):
        report(world, "T1", "T1", red)
        got = io.red_gap(world.sd, "T1", OWNS)
        assert (got == f"its red run `{red}` names no failing test") is gap, (red, got)
        assert (got is None) is (not gap)


def test_red_gap_none_message_uses_the_reports_text_and_three_files(world):
    report(world, "T1", "T1", "None - nothing to test")
    owns = ["a/Tests/AT.swift", "tests/b.py", "c_test.go", "d.spec.ts", "src/x.py"]
    assert io.red_gap(world.sd, "T1", owns) == ("its report says `None - nothing to test`, but it owns test files "
                                               "(a/Tests/AT.swift, tests/b.py, c_test.go)")


def test_contract_mentions_lists_other_tasks_code_blocks_and_skips_prose(world):
    extra = (f"\n### T3 use · Complexity 1 · Est. context 1k\n**Owns:** Sources/Use.swift\n{FENCE}swift\n"
             f"struct Use: Codable {{ let c: FooConfig }}\n{FENCE}\n")
    prose = "\nThe FooConfig design is described here.\n#### FooConfig heading\n"
    text = PLAN_TEXT.replace("## Package: core (library)", prose + "## Package: core (library)") + extra
    world.proj.joinpath("plan.md").write_text(text, encoding="utf-8")
    pl = pt.Plan.load(world.plan)
    rows = io.contract_mentions(pl, "T1")[1]
    assert [(w, t[:12]) for _, w, t in rows] == [("table", "| FooConfig "), ("T2", "**Consumes:*"),
                                                  ("T2", "**Steps:** 1"), ("T3", "struct Use: ")]
