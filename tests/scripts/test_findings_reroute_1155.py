"""#1155: a re-route of the same report keeps each finding's id and tier; a new report that repeats it raises."""
import hashlib
import json
import sys

from test_plan_tools import SCRIPTS
from test_findings_route import f, put, run  # noqa: F401  (the fixture)

sys.path.insert(0, str(SCRIPTS))
import finding_check as fc  # noqa: E402
import findings  # noqa: E402

QUOTE = "for i in range(n - 1):"


def brief(sd, name):
    return (sd / "briefs" / name).read_text(encoding="utf-8")


def a_finding(problem="off by one"):
    return f("src/a.py", 12, 1, problem, quote=QUOTE)


def test_report_src_1155():
    assert findings.report_src("FR1", []) == "FR1@" + hashlib.sha256(b"[]").hexdigest()[:12] == "FR1@4f53cda18c2b"
    assert findings.report_src("FR1", "nope") == findings.report_src("FR1", [])
    one = findings.report_src("FR1", [{"a": 1, "b": 2}])
    assert one == findings.report_src("FR1", [{"b": 2, "a": 1}])
    assert one != findings.report_src("FR2", [{"a": 1, "b": 2}])
    assert one != findings.report_src("FR1", [{"a": 1, "b": 3}])


def test_reroute_with_also_keeps_tier_and_id_1155(run):
    root, sd, plan, report = run
    r1 = report("FR1", [a_finding()])
    l1 = findings.route(sd, plan, [r1], "/sl/sl")
    l2 = findings.route(sd, plan, [r1], "/sl/sl", also=["src/c.py"])
    b = sd.resolve() / "briefs" / "fix-F-T1-1.md"
    assert l1[0].startswith(f"fixer tier=sonnet brief={b} ")
    assert l2[0].startswith(f"fixer tier=sonnet brief={b} ")
    assert " files=src/a.py,src/c.py " in l2[0]
    text = brief(sd, "fix-F-T1-1.md")
    assert "src/c.py" in text and "(tier 1, from FR1)" in text and "repeat of" not in text
    assert not (sd / "briefs" / "fix-F-T1-2.md").exists()
    rows = fc.load(sd)
    assert [r["id"] for r in rows] == ["F-T1-1", "F-T1-1"]
    assert [r["tier"] for r in rows] == [1, 1] and [r["round"] for r in rows] == [1, 2]
    src = findings.report_src("FR1", json.loads(open(r1).read())["findings"])
    assert all(r["srcs"] == [src] for r in rows)


def test_reroute_through_cli_keeps_tier_and_id_1155(run, capsys):
    root, sd, plan, report = run
    r1 = report("FR1", [a_finding()])
    assert findings.main(["route", "--plan", str(plan), r1]) == 0
    capsys.readouterr()
    assert findings.main(["route", "--plan", str(plan), "--also", "src/c.py", r1]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert out[0].startswith("fixer tier=sonnet ") and "fix-F-T1-1.md" in out[0]


def test_new_report_still_raises_a_repeat_1155(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [a_finding()])], "/sl/sl")
    r2 = report("FR2", [a_finding()])
    assert findings.route(sd, plan, [r2], "/sl/sl")[0].startswith("fixer tier=sonnet-high ")
    text = brief(sd, "fix-F-T1-2.md")
    assert "repeat of F-T1-1" in text and "(tier 2," in text
    again = findings.route(sd, plan, [r2], "/sl/sl")
    assert again[0].startswith("fixer tier=sonnet-high ") and "fix-F-T1-2.md" in again[0]
    assert "repeat of F-T1-1" in brief(sd, "fix-F-T1-2.md")


def test_rewritten_report_same_label_raises_1155(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [a_finding()])], "/sl/sl")
    r1 = report("FR1", [a_finding("off by one again")])
    lines = findings.route(sd, plan, [r1], "/sl/sl")
    assert lines[0].startswith("fixer tier=sonnet-high ") and "fix-F-T1-2.md" in lines[0]


def test_old_and_new_report_together_raise_1155(run):
    root, sd, plan, report = run
    r1 = report("FR1", [a_finding()])
    findings.route(sd, plan, [r1], "/sl/sl")
    r2 = report("FR2", [a_finding()])
    lines = findings.route(sd, plan, [r1, r2], "/sl/sl")
    assert len(lines) == 1 and lines[0].startswith("fixer tier=sonnet-high ")
    assert "fix-F-T1-2.md" in lines[0] and "repeat of F-T1-1" in brief(sd, "fix-F-T1-2.md")


def test_reroute_mixed_with_a_new_finding_1155(run):
    root, sd, plan, report = run
    r1 = report("FR1", [a_finding()])
    findings.route(sd, plan, [r1], "/sl/sl")
    r3 = report("FR3", [f("src/a.py", 30, 1, "leak", quote="x = open(p)")])
    lines = findings.route(sd, plan, [r1, r3], "/sl/sl")
    assert len(lines) == 1 and lines[0].startswith("fixer tier=sonnet ") and "fix-F-T1-1.md" in lines[0]
    text = brief(sd, "fix-F-T1-1.md")
    assert "F-T1-1 src/a.py:12" in text and "F-T1-2 src/a.py:30" in text


def test_legacy_rows_without_srcs_still_raise_1155(run):
    root, sd, plan, report = run
    r1 = report("FR1", [a_finding()])
    findings.route(sd, plan, [r1], "/sl/sl")
    p = sd / "findings.jsonl"
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    for r in rows:
        r.pop("srcs", None)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    lines = findings.route(sd, plan, [r1], "/sl/sl")
    assert lines[0].startswith("fixer tier=sonnet-high ") and "fix-F-T1-2.md" in lines[0]


def test_screen_without_srcs_still_raises_1155(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [a_finding()])], "/sl/sl")
    out, _ = findings.screen([{**a_finding(), "label": "FR1"}], root, sd)
    assert len(out) == 1 and out[0]["tier"] == 2 and out[0]["repeat"] == "F-T1-1"
