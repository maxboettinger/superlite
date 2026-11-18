"""FD3: findings.screen and the ledger: quotes proven, one fingerprint once, repeats raised, dismissals kept."""
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


def fp_of(file="src/a.py", quote=QUOTE):
    return fc.fingerprint(file, quote)


def test_final_review_finding_without_quote_is_not_briefed(run, capsys):
    root, sd, plan, report = run
    r = report("FR1", [f("src/a.py", 12, 1, "off by one", quote="")])
    assert findings.main(["route", "--plan", str(plan), r]) == 0
    cap = capsys.readouterr()
    assert cap.out.strip() == "findings: none routed (1 unverified, 0 dismissed)"
    assert "UNVERIFIED src/a.py:12 - off by one (no quote) from FR1" in cap.err
    assert not list(sd.glob("briefs/fix-*.md"))
    rows = fc.load(sd)
    assert [r["state"] for r in rows] == ["unverified"]


def test_other_reports_route_without_a_quote(run):
    root, sd, plan, report = run
    lines = findings.route(sd, plan, [report("T3", [f("src/a.py", 12, 1, "off by one", quote="")])], "/sl/sl")
    assert len(lines) == 1
    row = fc.load(sd)[0]
    assert row["state"] == "routed" and row["fp"] == fc.fingerprint("src/a.py", "", "off by one")


def test_moved_quote_corrects_the_line(run):
    root, sd, plan, report = run
    put(root, "src/a.py", 40, QUOTE)
    r = report("FR1", [{**f("src/a.py", 12, 1, "off by one"), "quote": QUOTE}])
    # report() wrote the quote on line 12 too; remove it so only line 40 holds it
    (root / "src" / "a.py").write_text("\n" * 39 + QUOTE)
    findings.route(sd, plan, [r], "/sl/sl")
    assert "- F-T1-1 src/a.py:40 - off by one" in brief(sd, "fix-F-T1-1.md")


def test_one_fingerprint_twice_becomes_one_finding_at_the_highest_tier(run):
    root, sd, plan, report = run
    put(root, "src/a.py", 12, QUOTE)
    two = [{**f("src/a.py", 12, 1, "first"), "quote": QUOTE, "label": "FR1"},
           {**f("src/a.py", 12, 2, "second"), "quote": QUOTE, "label": "FR1"}]
    out, notes = findings.screen(two, root, sd)
    assert len(out) == 1 and out[0]["tier"] == 2 and notes == []


def test_repeat_moves_up_one_tier_and_names_the_earlier_id(run):
    root, sd, plan, report = run
    r1 = report("T1", [f("src/a.py", 12, 1, "off by one", quote=QUOTE)])
    assert findings.route(sd, plan, [r1], "/sl/sl")[0].startswith("fixer tier=sonnet ")
    lines = findings.route(sd, plan, [r1], "/sl/sl")
    assert lines[0].startswith("fixer tier=sonnet-high ")
    text = brief(sd, "fix-F-T1-2.md")
    assert "repeat of F-T1-1" in text and "(tier 2," in text
    lines = findings.route(sd, plan, [r1], "/sl/sl")
    assert lines[0].startswith("fixer tier=opus ")
    lines = findings.route(sd, plan, [r1], "/sl/sl")
    assert lines[0].startswith("fixer tier=opus ")
    assert [r["round"] for r in fc.load(sd)] == [1, 2, 3, 4]


def test_dismissed_fingerprint_is_dropped(run, capsys):
    root, sd, plan, report = run
    r1 = report("T1", [f("src/a.py", 12, 1, "off by one", quote=QUOTE)])
    findings.route(sd, plan, [r1], "/sl/sl")
    capsys.readouterr()
    fp = fp_of()
    assert findings.main(["dismiss", fp, "--ruling", "not a defect", "--plan", str(plan)]) == 0
    capsys.readouterr()
    assert findings.main(["route", "--plan", str(plan), r1]) == 0
    cap = capsys.readouterr()
    assert f"DISMISSED {fp} src/a.py:12 - off by one (ruled: not a defect)" in cap.err
    assert cap.out.strip() == "findings: none routed (0 unverified, 1 dismissed)"
    assert not (sd / "briefs" / "fix-F-T1-2.md").exists()


def test_dismiss_records_ruling_and_refuses_unknown_fp(run, capsys):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("T1", [f("src/a.py", 12, 1, "off by one", quote=QUOTE)])], "/sl/sl")
    fp = fp_of()
    assert findings.main(["dismiss", fp, "--ruling", "not a defect", "--plan", str(plan)]) == 0
    assert fc.load(sd)[-1]["state"] == "dismissed"
    assert f"- Ruling: finding {fp} src/a.py:12 dismissed - not a defect" in (sd / "progress.md").read_text()
    assert findings.main(["dismiss", "ffffffffff", "--ruling", "x", "--plan", str(plan)]) == 2
    assert findings.main(["dismiss", fp, "--ruling", "  ", "--plan", str(plan)]) == 2
    capsys.readouterr()


def test_rounds_markdown(run, capsys, tmp_path):
    root, sd, plan, report = run
    assert findings.main(["rounds", "--plan", str(plan)]) == 0
    assert capsys.readouterr().out.strip() == "rounds: none"
    r1 = report("T1", [f("src/a.py", 12, 1, "off by one", quote=QUOTE)])
    findings.route(sd, plan, [r1], "/sl/sl")
    findings.route(sd, plan, [r1], "/sl/sl")
    capsys.readouterr()
    out_file = tmp_path / "rounds.md"
    assert findings.main(["rounds", "--plan", str(plan), "--out", str(out_file)]) == 0
    out = capsys.readouterr().out
    fp = fp_of()
    assert "## Round 1" in out and "## Round 2" in out
    assert f"- F-T1-1 src/a.py:12 - off by one (tier 1) fp {fp}: routed" in out
    assert out.strip() == out_file.read_text().strip()


def test_brief_line_carries_quote_and_fingerprint(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 12, 1, "off by one", quote=QUOTE)])], "/sl/sl")
    line = next(ln for ln in brief(sd, "fix-F-T1-1.md").splitlines() if ln.startswith("- F-T1-1"))
    assert line.endswith(f"quote: `{QUOTE}` fp: {fp_of()}")


def test_fix_brief_has_corrections(run):
    root, sd, plan, report = run
    (root / "docs" / "superlite").mkdir(parents=True)
    (root / "docs" / "superlite" / "corrections.md").write_text("# Corrections\n\n- Use uv, never pip\n")
    (sd / "briefs").mkdir()
    import backlog_brief as bb
    (sd / "briefs" / "lead.md").write_text(f"{bb.NOTE_HEAD}\n    a note\n", encoding="utf-8")
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T1-1.md")
    sec = "## Corrections (binding, from the user)\n\n- Use uv, never pip"
    assert text.count(sec) == 1 and text.index("a note") < text.index(sec) < text.index("Findings:")
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"state": "busy", "role": "implementer", "task": "T3"}}}))
    findings.route(sd, plan, [report("FR2", [f("src/d.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-C-1.md")
    assert text.count(sec) == 1 and text.index("a note") < text.index(sec) < text.index("Findings:")


def test_route_without_ledger_or_corrections_file_still_works(run):
    root, sd, plan, report = run
    assert not (sd / "findings.jsonl").exists()
    lines = findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    assert len(lines) == 1 and "Corrections" not in brief(sd, "fix-F-T1-1.md")
