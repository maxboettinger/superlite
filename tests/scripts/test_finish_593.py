"""finish: a recorded or later run never replaces the last full run; commits after it are named; open incidents
leave out gone files and ledger-ruled locations like the packet (#593, B127 follow-up)."""
import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402

FULL = "- tests full passed=3893 failed=0 skipped=8 seconds=812.3"
REC = "- tests integration passed=1 failed=0 skipped=0 seconds=4 recorded"
OLDREC = "- tests full passed=1 failed=0 skipped=0 seconds=4 recorded"
FAST = "- tests fast passed=12 failed=0 skipped=0 seconds=1.2"
C3 = "- commit T3 abc1234 fix the parser"
C4 = "- commit T4 def5678 more"


def ledger(tmp_path, *lines):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    p = sl / "progress.md"
    p.write_text("# Progress ledger\n- start abc1234\n" + "".join(x + "\n" for x in lines), encoding="utf-8")
    return p


def git(root, *a):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


def entry(file, line):
    return {"file": file, "line": line, "kind": "exception", "resolution": "open", "context": "boom"}


def test_recorded_runs_never_replace_the_full_run(tmp_path):
    for rec in (REC, OLDREC):
        res, newer, n = finish.test_result(ledger(tmp_path, FULL, rec, FAST))
        assert (res["mode"], res["passed"], res["recorded"]) == ("full", 3893, False)
        assert newer["mode"] == "fast" and n == 2


def test_only_recorded_and_fast_lines_give_the_newest_line(tmp_path):
    res, newer, n = finish.test_result(ledger(tmp_path, FAST, REC))
    assert (res["mode"], res["passed"], res["recorded"]) == ("integration", 1, True) and newer is None and n == 0


def test_commits_after_full(tmp_path):
    assert finish.commits_after_full(ledger(tmp_path, C3, FULL, FAST)) == []
    assert finish.commits_after_full(ledger(tmp_path, FULL, C3, FAST, C4, C3)) == ["T3", "T4"]
    assert finish.commits_after_full(ledger(tmp_path, C3, FAST)) == []
    assert finish.commits_after_full(ledger(tmp_path, FULL, OLDREC, C3)) == ["T3"]
    assert finish.commits_after_full(tmp_path / "missing" / "progress.md") == []


def test_finish_prints_the_full_run_a_newer_recorded_run_and_the_commits(tmp_path):
    p = ledger(tmp_path, FULL, C3, REC)
    cp = run(SCRIPTS / "finish.py", "--ledger", p, "--log", p.with_name("incidents.jsonl"), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    out = cp.out.splitlines()
    i = out.index("tests (full): 3893 passed, 0 failed, 8 skipped in 812.3s")
    assert out[i + 1] == "- newer recorded integration run (not the run's result): 1 passed, 0 failed, 0 skipped in 4.0s"
    assert out[i + 2] == "- committed after this full run: T3 (it does not cover them; rerun sl run_tests --full)"


def test_finish_without_commits_after_the_full_run_prints_no_commit_line(tmp_path):
    p = ledger(tmp_path, C3, FULL)
    cp = run(SCRIPTS / "finish.py", "--ledger", p, "--log", p.with_name("incidents.jsonl"), cwd=tmp_path)
    assert "committed after this full run" not in cp.out


def test_open_incidents_drop_gone_files_and_ruled_locations(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
    p = ledger(tmp_path, "- Ruling: b.py:3 is intended (B127)")
    log = p.with_name("incidents.jsonl")
    log.write_text("".join(json.dumps(entry(f, n)) + "\n" for f, n in (("a.py", 1), ("b.py", 3), ("gone.py", 2), ("b.py", 30))), encoding="utf-8")
    assert [(e["file"], e["line"]) for e in finish.open_incidents(log)] == [("a.py", 1), ("b.py", 30)]


def test_open_incidents_outside_git_keep_missing_files(tmp_path):
    p = ledger(tmp_path)
    log = p.with_name("incidents.jsonl")
    log.write_text(json.dumps(entry("gone.py", 2)) + "\n", encoding="utf-8")
    assert [e["file"] for e in finish.open_incidents(log)] == ["gone.py"]


def test_open_incidents_normalize_paths_like_the_packet(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    p = ledger(tmp_path, f"- Ruling: a.py:5 is intended (B127)")
    log = p.with_name("incidents.jsonl")
    rows = [("./a.py", 1), (str(tmp_path.resolve() / "a.py"), 2), ("./a.py", 5), ("./gone.py", 3)]
    log.write_text("".join(json.dumps(entry(f, n)) + "\n" for f, n in rows), encoding="utf-8")
    assert [(e["file"], e["line"]) for e in finish.open_incidents(log)] == [("a.py", 1), ("a.py", 2)]


def test_open_incidents_use_the_ledger_finish_was_given(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
    p = ledger(tmp_path, "- Ruling: b.py:3 is intended (F-T2-1)")
    logdir = tmp_path / "other"
    logdir.mkdir()
    log = logdir / "incidents.jsonl"
    log.write_text(json.dumps(entry("b.py", 3)) + "\n", encoding="utf-8")
    assert finish.open_incidents(log) != []
    assert finish.open_incidents(log, ledger=p) == []
    cp = run(SCRIPTS / "finish.py", "--ledger", p, "--log", log, cwd=tmp_path)
    assert "open incidents: 0" in cp.out, cp.both
