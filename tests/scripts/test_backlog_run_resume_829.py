# tests/scripts/test_backlog_run_resume_829.py
import json, os, sys
from pathlib import Path
from test_backlog_run import GIT, bk, brief_of, git, parked, run  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402

CP = "- Checkpointed tasks (ledger .superlite/progress.md; hidden checkpoints are not in the commits above): "
RV = "- Reviews (.superlite/fleet/reports): "
FR = "- Last full run ({}): {}"
STEPS = "- Steps left after the park: "


def ledger(sd, *lines):
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "progress.md").write_text("# ledger\n" + "\n".join(lines) + "\n", encoding="utf-8")


def report(sd, name, body, mt=None):
    d = sd / "fleet" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    if mt:
        os.utime(f, (mt, mt))


def test_progress_lines_examples(tmp_path):
    sd = tmp_path / ".superlite"
    ledger(sd, "- commit T1 abc1234567 ship guard", "- commit T2 def4567890 brief text")
    report(sd, "FR1.json", {"role": "final-reviewer", "label": "FR1", "status": "APPROVED"})
    assert br._progress_lines(sd) == [
        CP + "2: T1 abc1234567 ship guard; T2 def4567890 brief text",
        RV + "1: FR1 APPROVED (final-reviewer)",
        FR.format(".superlite/test-summary-full.json", "none"),
        STEPS + "full suite, ship"]
    assert br._progress_lines(tmp_path / "empty") == [
        CP + "0", RV + "0", FR.format(".superlite/test-summary-full.json", "none"), STEPS + "final review, full suite, ship"]


def test_progress_lines_cap_and_recheckpoint(tmp_path):
    sd = tmp_path / ".superlite"
    ledger(sd, *[f"- commit T{i} aaa000000{i} title {i}" for i in range(1, 8)], "- commit T1 fff0000000 ship guard v2",
           "- commit T3 bbb0000000 bad \x1b[31m title")
    first = br._progress_lines(sd)[0]
    assert first.startswith(CP + "7: T1 fff0000000 ship guard v2; T2 aaa0000002 title 2; T3 bbb0000000 bad ?[31m title; T4 ")
    assert first.endswith("T5 aaa0000005 title 5 (+2 more)")


def test_full_run_green_drops_full_suite(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    report(sd, "FR1.json", {"role": "final-reviewer", "label": "FR1", "status": "APPROVED"})
    (sd / "test-summary-full.json").write_text(json.dumps({"mode": "full", "passed": 812, "failed": 0}))
    out = br._progress_lines(sd)
    assert out[2] == FR.format(".superlite/test-summary-full.json", "812 passed, 0 failed") and out[3] == STEPS + "ship"
    (sd / "test-summary-full.json").write_text(json.dumps({"mode": "full", "passed": 800, "failed": 3}))
    out = br._progress_lines(sd)
    assert out[2].endswith("800 passed, 3 failed") and out[3] == STEPS + "full suite, ship"
    (sd / "test-summary-full.json").unlink()
    (sd / "test-summary.json").write_text(json.dumps({"mode": "full", "passed": 5, "failed": 0}))
    out = br._progress_lines(sd)
    assert out[2] == FR.format(".superlite/test-summary.json", "5 passed, 0 failed") and out[3] == STEPS + "ship"
    (sd / "test-summary.json").write_text(json.dumps({"mode": "fast", "passed": 5, "failed": 0}))
    out = br._progress_lines(sd)
    assert out[2].endswith(": none") and out[3] == STEPS + "full suite, ship"


def test_progress_lines_skip_bad_files(tmp_path):
    sd = tmp_path / ".superlite"
    report(sd, "bad.json", "{not json")
    report(sd, "norole.json", {"label": "X", "status": "DONE"})
    report(sd, "impl.json", {"role": "implementer", "label": "T2", "status": "DONE"})
    report(sd, "T1.json", {"role": "package-reviewer", "label": "T1", "status": "DONE"})
    assert br._progress_lines(sd)[1] == RV + "1: T1 DONE (package-reviewer)"
    for i in range(7):
        report(sd, f"P{i}.json", {"role": "package-reviewer", "label": f"P{i}", "status": "DONE"}, mt=1000 + i)
    os.utime(sd / "fleet" / "reports" / "T1.json", (500, 500))
    rv = br._progress_lines(sd)[1]
    assert rv.startswith(RV + "8: (+3 earlier); P2 DONE") and rv.endswith("P6 DONE (package-reviewer)")
    report(sd, "FR.json", {"role": "final-reviewer", "label": "FR", "status": "APPROVED (partial: lines 1-9 not read)"}, mt=2000)
    assert br._progress_lines(sd)[3] == STEPS + "final review, full suite, ship"


def test_resume_brief_lists_checkpoints_after_uncommitted(bk, capsys, monkeypatch):
    wt = parked(bk, questions=1, answers={"Keep the v1 API?": "Drop"})
    (wt / ".superlite" / "answer-1.json").write_text("{}")
    ledger(wt / ".superlite", "- commit T1 abc1234567 ship guard")
    monkeypatch.setattr(br, "_run", git(GIT))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    unc = "- Uncommitted files: 2: M skills/x.py, ?? tests/y.py\n"
    assert unc + CP + "1: T1 abc1234567 ship guard\n" + RV + "0\n" in text
    assert text.index(STEPS) < text.index("- Answers given mid-run")


def test_progress_lines_return_annotation_is_list_of_str():
    import inspect
    assert inspect.signature(br._progress_lines).return_annotation in (list[str], "list[str]")


def test_progress_lines_survive_deeply_nested_json(tmp_path):
    sd = tmp_path / ".superlite"
    deep = "[" * 200000 + "]" * 200000
    report(sd, "deep.json", deep)
    (sd / "test-summary-full.json").write_text(deep, encoding="utf-8")
    out = br._progress_lines(sd)
    assert out[1] == RV + "0"
    assert out[2] == FR.format(".superlite/test-summary-full.json", "none")
