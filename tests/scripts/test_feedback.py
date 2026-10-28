import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="fake ssh and gh are sh scripts")
SCRIPT = (Path(__file__).resolve().parents[2] / "skills"
          / "subagent-driven-development" / "scripts" / "feedback.py")


def run(*args, cwd=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=cwd, env=e)


def inbox():
    return Path(os.environ["SUPERLITE_HOME"]) / "feedback.jsonl"


def entries():
    return [json.loads(x) for x in inbox().read_text(encoding="utf-8").splitlines()]


def triage(tmp_path, *args, issues=()):
    f = tmp_path / "issues.json"
    f.write_text(json.dumps(list(issues)), encoding="utf-8")
    r = run("triage", "--issues", str(f), *args, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_add_writes_entry_with_context(tmp_path):
    proj = tmp_path / "myproj"
    (proj / ".git").mkdir(parents=True)
    (proj / "sub").mkdir()
    r = run("add", "dispatch printed the same agent twice", "--kind", "bug",
            "--plan", "docs/plans/x.md", cwd=proj / "sub",
            env={"SUPERLITE_SESSION_ID": "s1", "SUPERLITE_HARNESS": "codex"})
    assert r.returncode == 0, r.stderr
    assert "feedback logged" in r.stdout and "1 untriaged" in r.stdout
    [e] = entries()
    assert e["text"] == "dispatch printed the same agent twice"
    assert e["kind"] == "bug" and e["harness"] == "codex" and e["session"] == "s1"
    assert e["project"] == "myproj" and e["plan"] == "x.md"
    assert e["version"] and e["host"] and e["date"] and len(e["id"]) == 12


def test_add_project_of_a_linked_worktree_is_the_repo(tmp_path):
    repo = tmp_path / "realrepo"
    (repo / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {repo / '.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")
    assert run("add", "x y z", cwd=wt).returncode == 0
    assert entries()[0]["project"] == "realrepo"


def test_add_scrubs_private_details(tmp_path):
    text = "failed in /Users/alice/work/secret/a.py and /home/bob/x, mail bob@corp.com token ghp_abcdefghijklmnop1234"
    assert run("add", text, cwd=tmp_path).returncode == 0
    t = entries()[0]["text"]
    assert "alice" not in t and "bob" not in t and "ghp_" not in t
    assert "~/work/secret/a.py" in t and "<email>" in t and "<secret>" in t


def test_add_rejects_empty_and_bad_kind(tmp_path):
    assert run("add", "  ", cwd=tmp_path).returncode == 2
    r = run("add", "x", "--kind", "nope", cwd=tmp_path)
    assert r.returncode == 2 and "kind" in r.stderr


def test_add_truncates_long_text(tmp_path):
    run("add", "w " * 600, cwd=tmp_path)
    t = entries()[0]["text"]
    assert len(t) == 500 and t.endswith("…")


def test_triage_groups_duplicates_and_ranks_by_count(tmp_path):
    for t in ("commit_task rejects docs md update noridoc",
              "commit_task rejects the docs md update for noridoc rule",
              "commit_task rejects docs md update noridoc again",
              "lint marks draft tasks frozen"):
        assert run("add", t, cwd=tmp_path).returncode == 0
    out = triage(tmp_path)
    assert "4 untriaged entries, 2 groups" in out
    first, second = out.index("## 1. ×3"), out.index("## 2. ×1")
    assert first < second
    assert "lint marks draft tasks frozen" in out[second:]


def test_triage_matches_open_issue(tmp_path):
    run("add", "dispatch offers an agent it just evicted from the pool", cwd=tmp_path)
    out = triage(tmp_path, issues=[{"number": 46, "title": "dispatch offers an agent it just evicted"},
                                   {"number": 7, "title": "unrelated thing"}])
    assert "maybe #46" in out and "#7" not in out


def test_triage_new_group_says_new(tmp_path):
    run("add", "probe run hangs on windows", cwd=tmp_path)
    assert "issue: none (new)" in triage(tmp_path)


def test_mark_hides_entries_from_next_triage(tmp_path):
    run("add", "first problem here", cwd=tmp_path)
    run("add", "second unrelated issue there", cwd=tmp_path)
    ids = [e["id"] for e in entries()]
    r = run("mark", ids[0], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    out = triage(tmp_path)
    assert "1 untriaged entries" in out and "first problem" not in out
    assert "first problem" in triage(tmp_path, "--all")


def test_triage_empty_inbox(tmp_path):
    assert "0 untriaged entries" in triage(tmp_path)


@POSIX_ONLY
def test_triage_merges_remote_hosts_and_skips_unreachable(tmp_path):
    run("add", "local friction one", cwd=tmp_path)
    remote = {"v": 1, "id": "abcdefabcdef", "date": "2026-10-20T10:00:00Z", "host": "mini",
              "kind": "slow", "text": "remote slowness in run_tests", "version": "1.2.5",
              "harness": "pi", "project": "p", "session": "", "plan": ""}
    fake = tmp_path / "fake-ssh"
    fake.write_text("#!/bin/sh\n"
                    f"case \"$*\" in *mini*) echo '{json.dumps(remote)}';; *) exit 255;; esac\n",
                    encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    f = tmp_path / "issues.json"
    f.write_text("[]", encoding="utf-8")
    r = run("triage", "--issues", str(f), "--host", "mini", "--host", "gone", cwd=tmp_path,
            env={"SUPERLITE_SSH": str(fake)})
    assert r.returncode == 0, r.stderr
    assert "remote slowness" in r.stdout and "local friction" in r.stdout
    assert "gone" in r.stderr


@POSIX_ONLY
def test_triage_reads_hosts_file(tmp_path):
    home = Path(os.environ["SUPERLITE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "feedback-hosts").write_text("# my macs\nnowhere\n", encoding="utf-8")
    fake = tmp_path / "fake-ssh"
    fake.write_text("#!/bin/sh\nexit 255\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    f = tmp_path / "issues.json"
    f.write_text("[]", encoding="utf-8")
    r = run("triage", "--issues", str(f), cwd=tmp_path, env={"SUPERLITE_SSH": str(fake)})
    assert r.returncode == 0 and "nowhere" in r.stderr


def test_sl_launcher_runs_feedback(tmp_path):
    sl = SCRIPT.with_name("sl")
    r = subprocess.run(["bash", str(sl), "feedback", "add", "via sl"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert entries()[0]["text"] == "via sl"


def test_finish_asks_for_superlite_friction(tmp_path):
    finish = SCRIPT.with_name("finish.py")
    r = subprocess.run([sys.executable, str(finish), "--ledger", str(tmp_path / "none.md"),
                        "--log", str(tmp_path / "none.jsonl")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "superlite friction this run" in r.stdout and "sl feedback add" in r.stdout


def test_add_scrubs_more_secret_shapes(tmp_path):
    text = ("ghu_abcdefghijklmnop12 ghr_abcdefghijklmnop12 glpat-abcdefghijklmnop12 AKIAABCDEFGHIJKLMNOP "
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig Bearer abcdefghijkl1234 "
            "C:\\\\Users\\\\carol\\\\x C:/Users/dave/y /root/z")
    assert run("add", text, cwd=tmp_path).returncode == 0
    t = entries()[0]["text"]
    for leak in ("ghu_", "ghr_", "glpat-", "AKIA", "eyJ", "abcdefghijkl1234", "carol", "dave", "/root"):
        assert leak not in t, (leak, t)


def test_add_project_with_relative_gitdir(tmp_path):
    repo = tmp_path / "relrepo"
    (repo / ".git" / "worktrees" / "wt").mkdir(parents=True)
    wt = repo / "trees" / "wt"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/wt\n", encoding="utf-8")
    assert run("add", "x y z", cwd=wt).returncode == 0
    assert entries()[0]["project"] == "relrepo"


def test_triage_skips_malformed_inbox_lines(tmp_path):
    home = Path(os.environ["SUPERLITE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "feedback.jsonl").write_text('{"id": 5, "text": "x"}\n{"id": "a1", "text": ["y"]}\nnot json\n'
                                         '{"id": "b2", "text": "valid entry text"}\n', encoding="utf-8")
    out = triage(tmp_path)
    assert "1 untriaged entries" in out and "valid entry text" in out


def test_triage_bad_issues_file_is_unmatched_not_new(tmp_path):
    run("add", "probe run hangs on windows", cwd=tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    r = run("triage", "--issues", str(bad), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "unmatched" in r.stdout and "none (new)" not in r.stdout and "cannot read" in r.stderr


@POSIX_ONLY
def test_triage_gh_failure_is_unmatched_not_new(tmp_path):
    run("add", "probe run hangs on windows", cwd=tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\necho 'gh: not logged in' >&2\nexit 4\n", encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    r = run("triage", "--repo", "o/r", cwd=tmp_path, env={"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
    assert r.returncode == 0, r.stderr
    assert "unmatched" in r.stdout and "none (new)" not in r.stdout
    assert "not logged in" in r.stderr
