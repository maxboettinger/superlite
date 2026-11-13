from test_backlog_cli import bk, cli  # noqa: F401
from backlog_fixtures import batch
import backlog_state as bs


def _set(bk, **kw):
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"], "needs_decision", **kw)]}))


def test_decide_no_worktree(bk, capsys):
    _set(bk, worktree=None)
    assert cli(capsys, "decide", "--print", "--batch", "B1") == (0, "B1 has no open question\n")


def test_decide_missing_question_file(bk, tmp_path, capsys):
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)
    _set(bk, worktree=str(wt))
    assert cli(capsys, "decide", "--print", "--batch", "B1") == (0, "B1 has no open question\n")


def test_decide_worktree_gone(bk, tmp_path, capsys):
    _set(bk, worktree=str(tmp_path / "gone"))
    assert cli(capsys, "decide", "--print", "--batch", "B1") == (0, "B1 has no open question\n")


def test_decide_unknown_batch(bk, capsys):
    _set(bk)
    assert cli(capsys, "decide", "--print", "--batch", "B9") == (3, "BLOCKED: unknown batch B9\n")


def test_decide_bad_json_still_blocked(bk, tmp_path, capsys):
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "question.json").write_text("{")
    _set(bk, worktree=str(wt))
    rc, out = cli(capsys, "decide", "--print", "--batch", "B1")
    assert rc == 3 and out.startswith("BLOCKED: B1 question.json unreadable: ")
