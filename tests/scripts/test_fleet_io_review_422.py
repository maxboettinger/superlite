# tests/scripts/test_fleet_io_review_422.py
import json, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402

PLAN_TEXT = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T3
```

## Package: cli (CLI)

### T1 entry · Complexity 3 · Est. context 30k
**Owns:** src/app/cli.py

## Package: Core lib (library)

### T3 engine · Complexity 6 · Est. context 30k
**Owns:** src/core/engine.py, tests/test_engine.py

### T4 docs · Complexity 4 · Est. context 30k
**Owns:** docs/notes.md

## Review Focus
- core: state, encoding
"""

@pytest.fixture
def world(tmp_path):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    (proj / ".git").mkdir()
    plan = proj / "plan.md"; plan.write_text(PLAN_TEXT, encoding="utf-8")
    return type("W", (), {"proj": proj, "sd": sd, "plan": str(plan)})

def ledger(world, *lines):
    (world.sd / "progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def test_ledger_commits_keeps_each_commit_line_in_order(tmp_path):
    p = tmp_path / "progress.md"
    p.write_text("- start abc1234\n- commit T1 abc1234 lean launch\n- Ruling: x\n- commit T1 def5678 fix\n- commit T2 0123abc brief\n")
    assert io.ledger_commits(p) == {"T1": ["commit T1 abc1234 lean launch", "commit T1 def5678 fix"], "T2": ["commit T2 0123abc brief"]}
    assert io.ledger_commits(tmp_path / "nope.md") == {}

def test_review_reasons_names_complexity_seam_and_focus(world):
    assert io.review_reasons(world.plan, "T3") == ["Complexity 6", "seam T1↔T3", "Review Focus state"]
    assert io.review_reasons(world.plan, "T1") == ["seam T1↔T3"]
    assert io.review_reasons(world.plan, "T4") == []
    with pytest.raises(KeyError):
        io.review_reasons(world.plan, "T9")

def test_package_tasks_by_section(world):
    assert io.package_tasks(world.plan, "core lib") == ["T3", "T4"]
    assert io.package_tasks(world.plan, "Core Lib (library)") == ["T3", "T4"]
    assert io.package_tasks(world.plan, "nope") == []
    assert io.package_names(world.plan) == ["cli", "Core lib"]

def test_review_hints_skip_uncommitted_and_reviewed_tasks(world):
    ledger(world, "- commit T1 abc1234 a", "- commit T3 def5678 b", "- commit T0 1111111 c")
    (world.sd / "fleet.json").write_text(json.dumps({"workers": {"W5": {"role": "package-reviewer", "review": ["T1"]}}}))
    assert io.review_hints(world.sd, world.plan) == [("T3", ["Complexity 6", "seam T1↔T3", "Review Focus state"])]
    (world.sd / "fleet.json").write_text(json.dumps({"workers": {}}))
    assert io.review_hints(world.sd, world.plan) == [("T1", ["seam T1↔T3"]), ("T3", ["Complexity 6", "seam T1↔T3", "Review Focus state"])]

def test_review_brief_lines(world):
    ledger(world, "- commit T3 abc1234 engine")
    plan = str(Path(world.plan).resolve())
    (world.sd / "incidents.jsonl").write_text(json.dumps({"file": "src/core/engine.py", "line": 4, "kind": "unsure", "context": "c", "agent": "T3", "resolution": "open"}) + "\n")
    (world.sd / "probes").mkdir(); (world.sd / "probes" / "adapter.py").write_text("x")
    out = io.review_brief(world.sd, world.plan, ["T3"], "/sl/sl", "/sl")
    lines = out.splitlines()
    for want in ["# Review: T3", "SUPERLITE=/sl", f"PLAN={plan}", f"Root: {world.proj}", "sl (type it literally in every command): /sl/sl",
                 "Why: T3: Complexity 6; seam T1↔T3; Review Focus state", "- commit T3 abc1234 engine",
                 "Diffs: `git show <sha>` for each commit above, in Root.", f"Spec slice: `/sl/sl task T3 --plan {plan}`",
                 "Files in scope: src/core/engine.py, tests/test_engine.py", f"Probe adapter: {world.sd / 'probes' / 'adapter.py'}"]:
        assert want in lines, want
    i = lines.index("Incident hotspots (`/sl/sl incident hotspots --files src/core/engine.py,tests/test_engine.py`):")
    assert json.loads(lines[i + 1])["file"] == "src/core/engine.py"
    pk = io.review_brief(world.sd, world.plan, ["T3", "T4"], "/sl/sl", "/sl", package="Core lib").splitlines()
    assert "# Review: T3, T4 (package Core lib)" in pk and "Why: every committed task of package Core lib" in pk

def test_review_brief_without_ledger_adapter_or_incidents(world):
    lines = io.review_brief(world.sd, world.plan, ["T3"], "/sl/sl", "/sl").splitlines()
    assert "- (no commit line in progress.md)" in lines and "Probe adapter: none" in lines
    i = [n for n, l in enumerate(lines) if l.startswith("Incident hotspots")][0]
    assert lines[i + 1] == "(none)"

def test_review_brief_leaves_the_report_contract_to_the_agent(world):
    out = io.review_brief(world.sd, world.plan, ["T3"], "/sl/sl", "/sl")
    assert "APPROVED" not in out and "CHANGES_REQUESTED" not in out and "200 words" not in out
    assert [l for l in out.splitlines() if l.strip()][-1].startswith("Probe adapter:")


def test_review_reasons_without_a_taskgraph_block_does_not_exit(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("# P\n\n## Package: cli (CLI)\n\n### T1 entry · Complexity 6 · Est. context 30k\n**Owns:** src/app/cli.py\n", encoding="utf-8")
    assert io.review_reasons(str(p), "T1") == ["Complexity 6"]
