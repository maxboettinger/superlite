"""Packet section 4 reports the newest full run whatever ran later; newer runs and commits after it get one row each (#593)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import pt_review as pt  # noqa: E402


def s(mode="full", started=100.0, passed=3893, failed=0, skipped=8, **kw):
    return {"mode": mode, "started": started, "passed": passed, "failed": failed, "skipped": skipped, "failures": [], "files": {}, **kw}


FULL = s()
FAST = s("fast", 200.0, 12, 0, 0)
REC = s("recorded", 300.0, 1, 0, 0, scope="integration", recorded="pytest -m integration")
OLDREC = s("full", 400.0, 1, 0, 0, recorded="x.sh")
KILLED = s("full", 500.0, 0, 1, 0, error="run_tests stopped by SIGTERM")


def write(p, d):
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def test_full_and_newer_picks_the_newest_full_run_with_a_result():
    full, newer = pt.full_and_newer([FAST, REC, FULL, s(started=50.0, passed=1)])
    assert full is FULL and newer == [REC, FAST]
    assert pt.full_and_newer([OLDREC, KILLED, FULL]) == (FULL, [KILLED, OLDREC])
    assert pt.full_and_newer([FAST, REC]) == (None, [])
    assert pt.full_and_newer([]) == (None, [])


def test_full_and_newer_drops_repeated_copies():
    assert pt.full_and_newer([dict(FAST), FULL, dict(FAST), dict(FULL)]) == (FULL, [FAST])


def test_an_untimed_full_run_ranks_below_timed_ones():
    untimed = {k: v for k, v in s(passed=7).items() if k != "started"}
    assert pt.full_and_newer([untimed, FULL])[0] is FULL
    assert pt.full_and_newer([untimed, FAST]) == (untimed, [])


def test_section4_shows_the_full_run_and_one_newer_row(tmp_path):
    text, nfail = pt.read_test_summary(write(tmp_path / "test-summary.json", FAST), runs=[FAST, FULL])
    assert text == ("- passed 3893 · failed 0 · skipped 8\n"
                    "- newer fast run (not the full run's result): 12 passed, 0 failed, 0 skipped")
    assert nfail == 0


def test_section4_counts_several_newer_runs_and_labels_recorded_and_errors(tmp_path):
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", REC), runs=[REC, FAST, FULL])
    assert text.splitlines()[-1] == ("- 2 newer runs (not the full run's result), newest recorded integration: "
                                     "1 passed, 0 failed, 0 skipped")
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", FAST), runs=[FAST, KILLED, FULL])
    assert text.splitlines()[-1] == ("- 2 newer runs (not the full run's result), newest full: 0 passed, 1 failed, 0 skipped; "
                                     "error: run_tests stopped by SIGTERM")
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", KILLED), runs=[KILLED, FULL])
    assert text.splitlines()[0] == "- killed run, no result: run_tests stopped by SIGTERM"
    assert text.splitlines()[1:] == ["- newest run with a result:", "- passed 3893 · failed 0 · skipped 8"]


def test_section4_names_commits_after_the_full_run(tmp_path, monkeypatch):
    monkeypatch.setattr(finish, "commits_after_full", lambda ledger: ["T3", "T4"], raising=False)
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", FULL), runs=[FULL], ledger=tmp_path / "progress.md")
    assert text.splitlines()[-1] == "- committed after this full run: T3, T4 (it does not cover them; rerun run_tests --full)"
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", FULL), runs=[FULL])
    assert "committed after" not in text


def test_section4_without_a_full_run_keeps_the_fast_label_and_labels_a_recorded_run(tmp_path):
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", FAST), runs=[FAST])
    assert text.startswith("- full suite not run yet (it runs alongside this review); newest fast run:\n")
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", REC), runs=[REC])
    assert text == ("- recorded integration run outside run_tests (`pytest -m integration`), not the full suite:\n"
                    "- passed 1 · failed 0 · skipped 0")


def test_packet_section4_reads_the_full_run_a_later_fast_run_overwrote(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (tmp_path / "plan.md").write_text("# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n", encoding="utf-8")
    write(sl / "test-summary-full.json", {**FULL, "skipped_tests": []})
    write(sl / "test-summary.json", {**FAST, "skipped_tests": []})
    (sl / "progress.md").write_text("- tests full passed=3893 failed=0 skipped=8 seconds=812.3\n"
                                    "- tests fast passed=12 failed=0 skipped=0 seconds=1.2\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "pt_review.py"), "packet", "--plan", str(tmp_path / "plan.md"),
                        "--root", str(tmp_path), "--out", str(tmp_path / "packet.md")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    sec = (tmp_path / "packet.md").read_text(encoding="utf-8").split("## 4. Test summary\n", 1)[1].split("\n## 5.", 1)[0]
    assert "full suite not run yet" not in sec
    assert sec.startswith("- passed 3893 · failed 0 · skipped 8\n"
                          "- newer fast run (not the full run's result): 12 passed, 0 failed, 0 skipped")


def test_packet_section4_lists_tasks_committed_after_the_full_run(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (tmp_path / "plan.md").write_text("# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n", encoding="utf-8")
    write(sl / "test-summary-full.json", {**FULL, "skipped_tests": []})
    write(sl / "test-summary.json", {**FULL, "skipped_tests": []})
    (sl / "progress.md").write_text("- tests full passed=3893 failed=0 skipped=8 seconds=812.3\n"
                                    "- commit T1 abc1234 x\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "pt_review.py"), "packet", "--plan", str(tmp_path / "plan.md"),
                        "--root", str(tmp_path), "--out", str(tmp_path / "packet.md")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    sec = (tmp_path / "packet.md").read_text(encoding="utf-8").split("## 4. Test summary\n", 1)[1].split("\n## 5.", 1)[0]
    assert "- committed after this full run: T1 (it does not cover them; rerun run_tests --full)" in sec


def test_error_is_cut_at_120_and_a_recorded_summary_without_scope_says_external(tmp_path):
    long = s("full", 500.0, 0, 1, 0, error="e" * 300)
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", FULL), runs=[long, FULL])
    assert text.splitlines()[-1].endswith("error: " + "e" * 120)
    rec = {k: v for k, v in REC.items() if k != "scope"}
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", rec), runs=[rec])
    assert text.startswith("- recorded external run outside run_tests")
    text, _ = pt.read_test_summary(write(tmp_path / "test-summary.json", rec), runs=[rec, FULL])
    assert "- newer recorded external run (not the full run's result)" in text


def test_a_missing_run_summary_with_a_full_copy_still_reports_the_full_run(tmp_path):
    text, nfail = pt.read_test_summary(tmp_path / "missing.json", runs=[FAST, FULL])
    assert text.startswith("- passed 3893 · failed 0 · skipped 8\n- newer fast run")
    assert pt.read_test_summary(tmp_path / "missing.json", runs=[])[0].startswith("- no test summary recorded")


def test_newer_runs_are_distinct_by_key_not_by_whole_dict(tmp_path):
    a, b = {**FAST, "files": {"x": 1}}, {**FAST, "files": {"y": 2}}
    assert pt.full_and_newer([a, b, FULL]) == (FULL, [a])


def test_an_untimed_run_listed_before_the_full_run_is_newer():
    untimed = {k: v for k, v in s("fast", passed=2).items() if k != "started"}
    assert pt.full_and_newer([untimed, FULL]) == (FULL, [untimed])
    assert pt.full_and_newer([FULL, untimed]) == (FULL, [])
    assert pt.full_and_newer([untimed, FAST, FULL]) == (FULL, [FAST, untimed])


def test_an_error_path_run_keeps_the_592_rows_then_the_full_run_and_newer_runs(tmp_path):
    err = s("fast", 150.0, 0, 1, 0, error="no test command found: add one")
    green = s("fast", 200.0, 12, 0, 0)
    text, nfail = pt.read_test_summary(write(tmp_path / "test-summary.json", err), runs=[err, green, FULL])
    assert text.splitlines() == ["- run without a result: no test command found: add one",
                                 "- FAILING: no test command found: add one",
                                 "- newest run with a result:",
                                 "- passed 3893 · failed 0 · skipped 8",
                                 "- newer fast run (not the full run's result): 12 passed, 0 failed, 0 skipped"]
    assert nfail == 1


def test_an_incident_context_of_180_characters_shows_whole(tmp_path):
    ctx = "c" * 180
    items = pt.incident_items([{"file": "a.py", "line": 1, "kind": "exception", "resolution": "open", "context": ctx}])
    assert f"- [exception/open] {ctx}" in items[0].body
