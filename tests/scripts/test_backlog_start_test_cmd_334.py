# tests/scripts/test_backlog_start_test_cmd_334.py
# backlog start seeds the main checkout's .superlite/test-cmd.json into each new lead worktree (#334).
import sys
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run, br  # noqa: F401
import backlog  # noqa: E402

CFG = '{"language": "python", "test": "python3 -m pytest -q"}\n'


def test_start_seeds_the_main_test_cmd_before_the_brief_is_sent(bk, capsys, monkeypatch):
    (bk.sd / "test-cmd.json").write_text(CFG)
    put(bk, b("B1", ["a.py"]))
    seen = []
    f = bk.root / ".claude" / "worktrees" / "superlite-b1-t" / ".superlite" / "test-cmd.json"
    def send(sd, wid, brief, label=""):
        seen.append(f.read_text() if f.is_file() else None)
        return label
    monkeypatch.setattr(sys.modules["fleet_io"], "send_brief", send, raising=False)
    assert run(capsys, "start")[0] == 0
    assert seen == [CFG]


def test_start_keeps_a_test_cmd_the_worktree_already_has(bk, capsys):
    (bk.sd / "test-cmd.json").write_text(CFG)
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"; (wt / ".superlite").mkdir(parents=True)
    own = wt / ".superlite" / "test-cmd.json"; own.write_text('{"test": "lead own"}')
    put(bk, b("B1", ["a.py"], "parked", reason="tui red", worktree=str(wt)))
    assert run(capsys, "start", "B1")[0] == 0
    assert own.read_text() == '{"test": "lead own"}'


def test_start_seeds_nothing_when_the_main_checkout_has_no_test_cmd(bk, capsys):
    put(bk, b("B1", ["a.py"]))
    w1 = bk.root / ".claude" / "worktrees" / "superlite-b1-t"
    assert run(capsys, "start") == (0, f"B1 running lead=W1 worktree={w1}\n")
    assert not (w1 / ".superlite" / "test-cmd.json").exists()


def test_start_goes_on_with_one_stderr_line_when_the_copy_fails(bk, capsys, monkeypatch):
    (bk.sd / "test-cmd.json").write_text(CFG)
    put(bk, b("B1", ["a.py"]))
    def boom(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(backlog.shutil, "copyfile", boom)
    w1 = bk.root / ".claude" / "worktrees" / "superlite-b1-t"
    rc = br.main(["start"]); cap = capsys.readouterr()
    assert (rc, cap.out) == (0, f"B1 running lead=W1 worktree={w1}\n")
    import run_config
    rc0 = run_config.resolve(None, bk.root)
    line = f"run config: {rc0['id']} (lead {rc0['lead']['model']}, effort {rc0['lead']['effort']})\n"
    assert cap.err == line + f"test-cmd.json not seeded into {w1}: disk full\n"
    assert get(bk, "B1")["state"] == "running" and not (w1 / ".superlite" / "test-cmd.json").exists()
