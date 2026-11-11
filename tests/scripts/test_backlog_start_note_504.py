import shlex
import sys, types
import pytest
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
import backlog_brief as real_brief

HELP = "  --note FILE  standing note: FILE's text (at most 2000 characters) goes into every lead brief from now on; an empty file clears it (backlog.py)"


@pytest.fixture
def run(bk, monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(real_brief, "STANDING", {}, raising=False)
    ns = types.SimpleNamespace(routed=[], standing=[], exc=None, bk=bk)
    def main(argv):
        ns.routed.append(list(argv))
        ns.standing.append(dict(sys.modules["backlog_brief"].STANDING))
        if ns.exc:
            raise ns.exc
        return 0
    monkeypatch.setitem(sys.modules, "backlog_run", types.SimpleNamespace(main=main))
    monkeypatch.setitem(sys.modules, "backlog_brief", real_brief)
    p = bs.path(bk.root)
    def seed(d):
        d["batches"] = [{"id": "B1", "state": "planned", "issues": [1], "files": ["a.py"], "depends": [], "decisions": []}]
    bs.update(p, seed)
    return ns


def note(tmp_path, text, name="n.md"):
    f = tmp_path / name
    f.write_text(text)
    return f


def test_note_stored_and_stripped(run, capsys, tmp_path):
    f = note(tmp_path, "Use uv.\r\nNo emojis.\n\n")
    rc, out = cli(capsys, "start", "B1", "--note", str(f), "--cap", "1")
    want = {"note": "Use uv.\nNo emojis.", "owned": [{"id": "B1", "state": "planned", "files": ["a.py"]}]}
    assert rc == 0 and run.routed == [["start", "B1", "--cap", "1"]]
    assert out.splitlines()[0] == f"note: stored from {f.resolve()} (2 lines); every lead brief from now on carries it"
    assert run.standing == [want]
    rc, out = cli(capsys, "start", "B1", f"--note={f}", "--cap", "1")
    assert run.routed[1] == ["start", "B1", "--cap", "1"] and run.standing[1] == want


def test_stored_note_reused_and_cleared(run, capsys, tmp_path):
    f = note(tmp_path, "Use uv.")
    cli(capsys, "start", "B1", "--note", str(f))
    cli(capsys, "start", "B1")
    assert run.standing[1]["note"] == "Use uv."
    e = note(tmp_path, "", "e.md")
    rc, out = cli(capsys, "start", "B1", "--note", str(e))
    assert "note: cleared; lead briefs carry no note" in out and run.standing[2]["note"] == ""
    assert "note" not in load(run.bk)


def test_bad_note_refused(run, capsys, tmp_path):
    p = str(tmp_path / "missing.md")
    rc, out = cli(capsys, "start", "B1", "--note", p)
    assert rc == 2 and out.startswith(f"BLOCKED: --note {p} unreadable: ")
    big = note(tmp_path, "x" * 2001, "big.md")
    assert cli(capsys, "start", "B1", "--note", str(big)) == (2, f"BLOCKED: --note {big}: 2001 characters, at most 2000\n")
    assert cli(capsys, "start", "--note") == (2, "BLOCKED: --note needs a FILE\n")
    assert run.routed == [] and "note" not in load(run.bk)


def test_running_leads_named(run, capsys, tmp_path):
    def up(d):
        d["batches"].append({"id": "B2", "state": "running", "issues": [2], "files": [], "depends": [], "decisions": [], "lead": "W5"})
    bs.update(bs.path(run.bk.root), up)
    f = note(tmp_path, "Use uv.")
    out = cli(capsys, "start", "B1", "--note", str(f))[1]
    assert f'note: B2 lead W5 started before this note; sl backlog tell B2 --text "$(cat {shlex.quote(str(f.resolve()))})" tells it' in out
    d = tmp_path / "a b"
    d.mkdir()
    g = note(d, "Use uv.", "n'x.md")
    out = cli(capsys, "start", "B1", "--note", str(g))[1]
    assert f'"$(cat {shlex.quote(str(g.resolve()))})"' in out and "'" in shlex.quote(str(g.resolve()))
    out = cli(capsys, "start", "B1", "--note", str(note(tmp_path, "", "e.md")))[1]
    assert "started before this note" not in out


def test_worker_env_strips_without_storing(run, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W3")
    f = note(tmp_path, "Use uv.")
    assert cli(capsys, "start", "--note", str(f))[0] == 0
    assert run.routed == [["start"]] and "note" not in load(run.bk)


def test_start_help_names_note(run, capsys):
    run.exc = SystemExit(0)
    with pytest.raises(SystemExit) as e:
        bl.main(["start", "--help"])
    assert e.value.code == 0 and capsys.readouterr().out.endswith(HELP + "\n")
