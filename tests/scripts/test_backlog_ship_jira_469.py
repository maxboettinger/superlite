import json, sys, types
import pytest
from test_backlog_ship import sh, ship, b1, locked, AG  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_ship as bsh  # noqa: E402
import backlog_run  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402

VIEW = ["acli", "jira", "workitem", "view"]


def view(cat):
    return (0, json.dumps({"fields": {"status": {"statusCategory": {"key": cat}}}}))


def issues(sh, *ids, **kw):
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"issues": list(ids), **kw}))


def acli(sh, *verbs):
    return [c for c in sh.calls if c[:1] == ["acli"] and (not verbs or c[3] in verbs)]


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(backlog_run, "project_cleanup", lambda *a: None)


def test_with_closes_skips_jira_keys():
    assert bsh.with_closes("", [5, "PIX-1"]) == "Closes #5\n"
    assert bsh.with_closes("", ["PIX-1"]) == ""


def test_open_issues_reads_gh_and_acli(sh):
    sh.replies = {"gh issue view 5": (0, "CLOSED\n"), "gh issue view 6": (0, "OPEN\n"),
                  "acli jira workitem view PIX-1": view("done"), "acli jira workitem view PIX-2": view("new")}
    assert bsh.open_issues("o/r", [5, 6], sh.root) == [6]
    assert bsh.open_issues("o/r", ["PIX-1", "PIX-2"], sh.root) == ["PIX-2"]
    assert ["acli", "jira", "workitem", "view", "PIX-1", "--fields", "status", "--json"] in sh.calls
    sh.replies = {"acli jira workitem view PIX-1": (1, "boom"), "acli jira workitem view PIX-2": view("new")}
    assert bsh.open_issues("o/r", ["PIX-1", "PIX-2"], sh.root) == ["PIX-1", "PIX-2"]


def test_open_issues_retries_only_github_numbers(sh, monkeypatch):
    sleeps = []
    monkeypatch.setattr(bsh, "_sleep", sleeps.append)
    sh.replies = {"gh issue view": (0, "OPEN\n"), "acli jira workitem view": view("new")}
    assert bsh.open_issues("o/r", [5, "PIX-1"], sh.root) == [5, "PIX-1"] and sleeps == [10]
    assert len(acli(sh)) == 1
    sleeps.clear()
    assert bsh.open_issues("o/r", ["PIX-1"], sh.root) == ["PIX-1"] and sleeps == []
    assert bsh.open_issues("o/r", [5], sh.root, retry=False) == [5] and sleeps == []
    sh.replies = {"gh issue view": (0, "CLOSED\n")}
    assert bsh.open_issues("o/r", [5], sh.root) == [] and sleeps == []


def test_close_jira_comments_then_transitions_each_open_key(sh):
    sh.replies = {"acli jira workitem view": view("new")}
    assert bsh.close_jira("o/r", [5, "PIX-1"], 201, {"id": "B1", "version": "1.5.8"}, sh.root) == []
    assert sh.calls == [
        ["acli", "jira", "workitem", "view", "PIX-1", "--fields", "status", "--json"],
        ["acli", "jira", "workitem", "comment", "create", "--key", "PIX-1", "--body",
         "Shipped in https://github.com/o/r/pull/201 (superlite batch B1, version 1.5.8)."],
        ["acli", "jira", "workitem", "transition", "--key", "PIX-1", "--status", "Done", "--yes"]]


def test_close_jira_skips_a_key_already_done(sh):
    sh.replies = {"acli jira workitem view": view("done")}
    assert bsh.close_jira("o/r", ["PIX-1"], 201, {"id": "B1"}, sh.root) == []
    assert [c[3] for c in acli(sh)] == ["view"]


def test_close_jira_names_each_failed_step(sh):
    sh.replies = {"acli jira workitem view": view("new"), "acli jira workitem comment": (1, "boom\n"),
                  "acli jira workitem transition": (1, "denied\n")}
    assert bsh.close_jira("o/r", ["PIX-1"], 201, {"id": "B1"}, sh.root) == ["jira PIX-1: comment failed: boom", "jira PIX-1: transition failed: denied"]
    assert [c[3] for c in acli(sh)] == ["view", "comment", "transition"]


def test_merge_runs_the_cleanup_before_maxapp_ship_and_marks_cleaned(sh, capsys, monkeypatch):
    locked(sh, capsys)
    def fake(root, wt, branch, bid):
        sh.calls.append(("cleanup", str(wt), branch, bid)); return "B1 project cleanup: exit 3"
    monkeypatch.setattr(backlog_run, "project_cleanup", fake)
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"branch": "superlite/b1-x"}))
    sh.replies = {"maxapp ship": (0, "merged #201\n")}
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 0 and out.splitlines()[0] == "B1 project cleanup: exit 3"
    names = [c[0] for c in sh.calls]
    assert ("cleanup", str(sh.wt), "superlite/b1-x", "B1") in sh.calls and names.index("cleanup") < names.index("maxapp")
    assert b1(sh)["cleaned"] is True


def test_merge_jira_batch_closes_and_reports(sh, capsys, quiet, monkeypatch):
    locked(sh, capsys); issues(sh, "PIX-1", "PIX-2")
    states = {"PIX-1": [view("new"), view("done")], "PIX-2": [view("new")]}
    def run(cmd, cwd, timeout=None):
        sh.calls.append(cmd)
        if cmd[:1] == ["maxapp"]:
            return 0, "merged #201\n"
        if cmd[:4] == VIEW:
            s = states[cmd[4]]; return s.pop(0) if len(s) > 1 else s[0]
        if cmd[:4] == ["acli", "jira", "workitem", "transition"] and cmd[5] == "PIX-2":
            return 1, "no transition\nfor you\n"
        return 0, ""
    monkeypatch.setattr(bsh, "_run", run)
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 0 and out.endswith("OPEN PIX-2\njira PIX-2: transition failed: no transition / for you\n")
    maxapp = next(c for c in sh.calls if c[:1] == ["maxapp"])
    assert maxapp[maxapp.index("--title") + 1] == "B1: PIX-1 PIX-2"
    assert "Closes" not in (sh.sd / "backlog" / "B1.pr-body.md").read_text()
    assert b1(sh)["open_issues"] == ["PIX-2"]


def test_done_closes_jira_too(sh, capsys, quiet, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_ROLE", raising=False); monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setitem(sys.modules, "fleet", types.SimpleNamespace(stop=lambda sd, ids: None))
    monkeypatch.setattr(backlog_run, "_run", lambda cmd, cwd, timeout=None: (0, ""))
    issues(sh, "PIX-1", state="parked")
    ship_lock.acquire(sh.lock, {"batch": "B1", "lead": "W1", "agent": AG, "repo": "o/r"}, None, 9_000)
    sh.replies = {"gh pr view": (0, "MERGED\n"), "acli jira workitem view": view("new")}
    rc, out = ship(capsys, "B1", "done", "--pr", "201")
    assert rc == 0
    assert [c[3] for c in acli(sh)][:3] == ["view", "comment", "transition"]


def test_red_ship_leaves_cleaned_unset_so_done_cleans_later(sh, capsys, quiet):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (3, "RED: tests\n")}
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 6
    assert not b1(sh).get("cleaned")
