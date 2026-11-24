import shlex
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
from test_backlog_start_note_504 import run, note  # noqa: F401


def test_note_stores_and_starts_nothing(run, capsys, tmp_path):
    f = note(tmp_path, "Use uv.\nNo emojis.")
    rc, out = cli(capsys, "note", str(f))
    assert rc == 0 and run.routed == []
    assert out.splitlines() == [f"note: stored from {f.resolve()} (2 lines, 18 of 2000 characters); every lead brief from now on carries it"]
    assert load(run.bk)["note"]["text"] == "Use uv.\nNo emojis."
    assert [x["state"] for x in load(run.bk)["batches"]] == ["planned"]


def test_note_dev_null_clears(run, capsys, tmp_path):
    cli(capsys, "note", str(note(tmp_path, "Use uv.")))
    rc, out = cli(capsys, "note", "/dev/null")
    assert (rc, out) == (0, "note: cleared; lead briefs carry no note\n")
    assert "note" not in load(run.bk) and run.routed == []


def test_note_names_running_leads(run, capsys, tmp_path):
    bs.update(bs.path(run.bk.root), lambda d: d["batches"].append({"id": "B2", "state": "running", "lead": "W4", "issues": [2], "files": ["b.py"], "depends": [], "decisions": []}))
    f = note(tmp_path, "Use uv.")
    rc, out = cli(capsys, "note", str(f))
    src = shlex.quote(str(f.resolve()))
    assert rc == 0 and out.splitlines()[1] == f'note: B2 lead W4 started before this note; sl backlog tell B2 --text "$(cat {src})" tells it'


def test_note_refused_in_fleet_worker(run, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W3")
    rc, out = cli(capsys, "note", str(note(tmp_path, "x")))
    assert (rc, out) == (2, "BLOCKED: sl backlog note runs only in the main session\n") and "note" not in load(run.bk)


def test_bad_note_file_refused(run, capsys, tmp_path):
    p = str(tmp_path / "missing.md")
    rc, out = cli(capsys, "note", p)
    assert rc == 2 and out.startswith(f"BLOCKED: --note {p} unreadable:") and run.routed == []


def test_status_note_line_names_note_command():
    line = bs.note_line({"note": {"text": "a", "file": "/f", "time": "t"}})
    assert line.endswith("(sl backlog note FILE replaces it, an empty file clears it)")
