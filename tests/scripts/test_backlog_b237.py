import json
import pytest
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
import backlog_tracker


def seed_outside(bk, outside, batches=()):
    def fn(d):
        d["repo"] = "o/r"
        d["outside"] = outside
        d["batches"] = list(batches)
    bs.update(bs.path(bk.root), fn)


def planned(bid, issues, open_issues=None):
    b = {"id": bid, "topic": "t", "issues": issues, "files": [], "depends": [], "decisions": [], "state": "planned"}
    if open_issues is not None:
        b["open_issues"] = open_issues
    return b


LEFT = [{"number": 5, "title": "a", "reason": "not planned (cap)"}, {"number": 6, "title": "b", "reason": "not planned (triage)"}]


def test_status_note_names_characters():
    text = "a" * 1000 + "\n" + "b" * 449
    note = {"text": text, "file": "/m/rules.md", "time": "T"}
    assert bs.note_line({"note": note}) == (
        "note: 2 lines (1450 of 2000 characters) from /m/rules.md (T) go into every lead brief "
        "(sl backlog start --note FILE replaces it, an empty file clears it)")


def test_start_note_names_characters():
    text = "a" * 1000 + "\n" + "b" * 449
    assert bs.set_note({}, text, "/m/rules.md", "T") == (
        "note: stored from /m/rules.md (2 lines, 1450 of 2000 characters); every lead brief from now on carries it")


def test_status_drops_closed_left_out(bk, capsys, monkeypatch):
    seed_outside(bk, LEFT)
    monkeypatch.setattr(backlog_tracker, "open_now", lambda repo, issues, root: [6], raising=False)
    rc, out = cli(capsys, "status")
    assert rc == 0 and "not planned (triage): #6" in out
    assert "not planned (cap)" not in out and "cap:" not in out
    assert [o["number"] for o in load(bk)["outside"]] == [6]


def test_left_out_and_batches_one_call(bk, monkeypatch):
    seed_outside(bk, [LEFT[0]], [planned("B1", [1], [1])])
    calls = []
    def f(repo, issues, root):
        calls.append(list(issues))
        return list(issues)
    monkeypatch.setattr(backlog_tracker, "open_now", f, raising=False)
    bl.refresh_open(bk.root)
    assert calls == [[1, 5]]


def test_unreadable_left_out_kept(bk, monkeypatch):
    seed_outside(bk, LEFT)
    monkeypatch.setattr(backlog_tracker, "open_now", lambda repo, issues, root: list(issues), raising=False)
    bl.refresh_open(bk.root)
    assert load(bk)["outside"] == LEFT


def test_left_out_held_by_batch_not_asked(bk, monkeypatch):
    seed_outside(bk, [LEFT[0]], [planned("B1", [5], [5])])
    calls = []
    def f(repo, issues, root):
        calls.append(list(issues))
        return list(issues)
    monkeypatch.setattr(backlog_tracker, "open_now", f, raising=False)
    bl.refresh_open(bk.root)
    assert calls == [[5]]


BY = ('answers file: {"answers": {"<question>": "<option label>"}, "by": "user"}; "by" is required: '
      '"user" (the user answered), "main" (main ruled) or {"<question>": "user" | "main"}')


def test_decide_print_names_by(bk, capsys):
    bs.update(bs.path(bk.root), lambda d: d.update(outside=[{"number": 3, "title": "T", "author": "e"}]))
    rc = bl.main(["decide", "--print"])
    cap = capsys.readouterr()
    assert rc == 0 and json.loads(cap.out)["questions"]
    assert BY in cap.err.splitlines()


@pytest.mark.parametrize("argv", (["decide", "--help"], ["answer", "B", "--help"]))
def test_help_names_by(argv, capsys, monkeypatch):
    import backlog_run
    monkeypatch.setattr(bl, "_root", lambda: None)
    with pytest.raises(SystemExit):
        if argv[0] == "decide":
            bl.main(argv)
        else:
            backlog_run.main(argv)
    out = capsys.readouterr().out
    assert '"by"' in out and '"main"' in out
