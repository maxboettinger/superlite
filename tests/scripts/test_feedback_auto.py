"""Auto feedback (#140) and triage over closed issues (#182): `feedback.add_auto` logs a scrubbed entry of kind `auto`;
triage lists an auto group only from two entries on (signature = tool + reason, the target left out), and matches entry
ids against recently closed issues as well as open ones."""
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="fake gh is an env-python script")
SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS / "feedback.py"
sys.path.insert(0, str(SCRIPTS))
import feedback  # noqa: E402


def run(*args, cwd=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=cwd, env=e)


def entries():
    f = Path(os.environ["SUPERLITE_HOME"]) / "feedback.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()]


def triage(tmp_path, issues=()):
    f = tmp_path / "issues.json"
    f.write_text(json.dumps(list(issues)), encoding="utf-8")
    r = run("triage", "--issues", str(f), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return r.stdout


def put(eid, text, kind="bug", date="2026-11-01T10:00:00Z"):
    """An entry written straight into the inbox, as another host's would be."""
    f = Path(os.environ["SUPERLITE_HOME"]) / "feedback.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    row = {"v": 1, "id": eid, "date": date, "host": "h", "kind": kind, "text": text, "version": "1.5.6",
           "harness": "claude-code", "project": "p", "session": "", "plan": ""}
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def day(offset):
    """UTC date `offset` days ago, ISO."""
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - offset * 86400))


def fake_gh(tmp_path, closed, opened=()):
    """A `gh` on PATH answering `issue list`: `--state open` -> opened; `--state closed --search closed:>=D` -> the closed
    issues whose closedAt date is >= D (as the real search does). Every call's arguments land in gh.log."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    data = tmp_path / "gh-data.json"
    data.write_text(json.dumps({"open": list(opened), "closed": list(closed)}), encoding="utf-8")
    gh = bin_dir / "gh"
    gh.write_text("#!/usr/bin/env python3\n"
                  "import json, sys\n"
                  f"open({str(tmp_path / 'gh.log')!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                  f"d = json.load(open({str(data)!r}))\n"
                  "a = sys.argv[1:]\n"
                  "state = a[a.index('--state') + 1]\n"
                  "if state == 'open':\n"
                  "    out = d['open']\n"
                  "else:\n"
                  "    since = a[a.index('--search') + 1].split('>=')[1]\n"
                  "    out = [i for i in d['closed'] if i['closedAt'][:10] >= since]\n"
                  "print(json.dumps([{k: v for k, v in i.items() if k != 'closedAt'} for i in out]))\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def test_add_auto_scrubs():
    assert feedback.add_auto("block-coordinator-edits", "rule-block for max@example.com", "/Users/x/p/src/a.py", "1.5.6") is True
    [e] = entries()
    assert e["kind"] == "auto" and e["version"] == "1.5.6"
    assert e["target"] == "~/p/src/a.py" and "<email>" in e["reason"]
    assert "~/p/src/a.py" in e["text"] and "<email>" in e["text"] and "max@example.com" not in e["text"]
    assert "/Users/x" not in json.dumps(e) and "max@example.com" not in json.dumps(e)
    assert e["tool"] == "block-coordinator-edits" and e["id"] and e["host"]


def test_add_auto_twice_gives_two_entries(tmp_path):
    assert feedback.add_auto("block-coordinator-edits", "rule-block", "src/a.py", "1.5.6") is True
    assert feedback.add_auto("block-coordinator-edits", "rule-block", "src/a.py", "1.5.6") is True
    first, second = entries()
    assert first["id"] != second["id"]


def test_add_auto_refuses_an_empty_tool_and_survives_an_unwritable_inbox(tmp_path, monkeypatch):
    assert feedback.add_auto("", "rule-block", "src/a.py", "1.5.6") is False
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(blocker / "home"))  # a folder under a file cannot be made
    assert feedback.add_auto("run_tests", "no-result", "tests/x.py", "1.5.6") is False


def test_auto_groups_need_two(tmp_path):
    feedback.add_auto("block-coordinator-edits", "rule-block", "src/a.py", "1.5.6")
    put("aaaaaaaaaaaa", "probe run hangs on windows")  # a plain group of one is listed as before
    out = triage(tmp_path)
    assert "2 untriaged entries, 1 groups" in out
    assert "probe run hangs on windows" in out and "block-coordinator-edits" not in out
    feedback.add_auto("block-coordinator-edits", "rule-block", "src/b.py", "1.5.6")  # same tool and reason, another target
    feedback.add_auto("run_tests", "no-result", "tests/t.py", "1.5.6")  # a different signature stays a single
    out = triage(tmp_path)
    assert "4 untriaged entries, 2 groups" in out
    assert "×2 auto: block-coordinator-edits rule-block" in out
    assert "run_tests" not in out
    assert out.count("block-coordinator-edits") >= 1 and "src/b.py" in out


def test_auto_signature_leaves_the_target_out():
    a = {"kind": "auto", "tool": "t", "reason": "r", "target": "x"}
    b = {"kind": "auto", "tool": "t", "reason": "r", "target": "y"}
    c = {"kind": "auto", "tool": "t", "reason": "r2", "target": "x"}
    assert feedback.auto_sig(a) == feedback.auto_sig(b) != feedback.auto_sig(c)
    assert feedback.auto_sig({"kind": "bug", "tool": "t", "reason": "r"}) is None
    assert feedback.auto_sig({"kind": "auto", "text": "no fields"}) is None


@POSIX_ONLY
def test_triage_marks_closed_issue(tmp_path):
    put("abc123def456", "probe run hangs on windows")
    put("fff000fff000", "stale lock problem again here")
    env = fake_gh(tmp_path, closed=[
        {"number": 77, "title": "probe hangs", "body": "", "comments": [{"body": "Feedback entry: abc123def456"}], "closedAt": day(3) + "T08:00:00Z"},
        {"number": 12, "title": "stale lock", "body": "Feedback entry: fff000fff000", "comments": [], "closedAt": day(40) + "T08:00:00Z"}])
    r = run("triage", "--repo", "o/r", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert "## filed: #77" in r.stdout and "- ids: abc123def456" in r.stdout
    assert "sl feedback mark abc123def456`" in r.stdout  # the filed entry alone is offered for marking
    assert "#12" not in r.stdout  # closed 40 days ago: not fetched, so its entry stays a new group
    assert "- ids: fff000fff000" in r.stdout and "none (new)" in r.stdout
    calls = (tmp_path / "gh.log").read_text(encoding="utf-8").splitlines()
    closed = [c for c in calls if "--state closed" in c]
    assert len(closed) == 1 and f"closed:>={day(30)}" in closed[0] and "number,title,body,comments" in closed[0]


@POSIX_ONLY
def test_triage_open_and_closed_issues_both_name_entries(tmp_path):
    put("aaaaaaaaaaaa", "probe run hangs on windows")
    put("bbbbbbbbbbbb", "totally different stale lock problem")
    env = fake_gh(tmp_path, opened=[{"number": 5, "title": "x", "body": "cites aaaaaaaaaaaa", "comments": []}],
                  closed=[{"number": 6, "title": "y", "body": "", "comments": [{"body": "bbbbbbbbbbbb"}], "closedAt": day(1) + "T00:00:00Z"}])
    r = run("triage", "--repo", "o/r", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert "## filed: #5" in r.stdout and "## filed: #6" in r.stdout and "2 groups" in r.stdout
    assert "sl feedback mark aaaaaaaaaaaa bbbbbbbbbbbb" in r.stdout


@POSIX_ONLY
def test_closed_issue_failure_keeps_the_open_result(tmp_path):
    put("aaaaaaaaaaaa", "probe run hangs on windows")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncase \"$*\" in *closed*) echo 'gh: rate limit' >&2; exit 1;; esac\n"
                  "echo '[{\"number\": 5, \"title\": \"x\", \"body\": \"cites aaaaaaaaaaaa\", \"comments\": []}]'\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    r = run("triage", "--repo", "o/r", cwd=tmp_path, env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
    assert r.returncode == 0, r.stderr
    assert "## filed: #5" in r.stdout
    assert "closed issues not matched" in r.stderr


def test_triage_issues_file_is_not_extended_by_gh(tmp_path):
    put("aaaaaaaaaaaa", "probe run hangs on windows")
    out = triage(tmp_path, issues=[{"number": 3, "title": "x", "body": "aaaaaaaaaaaa"}])
    assert "## filed: #3" in out
