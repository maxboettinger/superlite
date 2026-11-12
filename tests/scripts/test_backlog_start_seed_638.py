# backlog start records the seeded bytes and tells the lead when the copy differs from main (#638).
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run, br  # noqa: F401
import testcmd  # noqa: E402

CFG = '{"language": "python", "test": "python3 -m pytest -q"}\n'


def test_start_records_seed_and_brief_note(bk, capsys, monkeypatch):
    monkeypatch.setattr(testcmd, "_main_checkout_root", lambda root: bk.root if testcmd.Path(root) != bk.root else None)
    (bk.sd / "test-cmd.json").write_text(CFG)
    put(bk, b("B1", ["a.py"]))
    assert run(capsys, "start")[0] == 0
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"
    assert (wt / ".superlite" / "test-cmd.seeded").read_text() == CFG == (wt / ".superlite" / "test-cmd.json").read_text()
    assert "Test command:" not in (wt / ".superlite" / "briefs" / "lead.md").read_text()


def test_parked_batch_with_differing_copy_gets_a_note(bk, capsys, monkeypatch):
    monkeypatch.setattr(testcmd, "_main_checkout_root", lambda root: bk.root if testcmd.Path(root) != bk.root else None)
    (bk.sd / "test-cmd.json").write_text(CFG)
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"; (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "test-cmd.json").write_text('{"test": "lead own"}')
    put(bk, b("B1", ["a.py"], "parked", reason="tui red", worktree=str(wt)))
    assert run(capsys, "start", "B1")[0] == 0
    lines = [ln for ln in (wt / ".superlite" / "briefs" / "lead.md").read_text().splitlines() if ln.startswith("Test command: ")]
    assert len(lines) == 1 and "differs from the main checkout's" in lines[0]
