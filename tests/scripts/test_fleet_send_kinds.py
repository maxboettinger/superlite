# tests/scripts/test_fleet_send_kinds.py
"""#292: `fleet send` takes task ids, --text or --brief, never two of them."""
import json
from test_fleet_io import world  # noqa: F401
import fleet_io as io

TWO = "error: send takes task ids, --text or --brief, not two of them\n"


def brief(w, name="b.md"):
    p = w.sd / "briefs"; p.mkdir(exist_ok=True); (p / name).write_text("do it\n"); return p / name


def untouched(w):
    assert not any(c[0] == "prompt" for c in w.fh.calls)
    assert json.loads((w.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"
    assert json.loads((w.sd / "pool.json").read_text())["agents"][0]["busy"] is False


def test_tasks_with_text_is_refused(world, capsys):
    assert io.main(["send", "W1", "T3", "--text", "x", "--plan", str(world.plan)]) == 2
    assert capsys.readouterr().err == TWO; untouched(world)


def test_tasks_with_brief_is_refused(world, capsys):
    assert io.main(["send", "W1", "T3", "--brief", str(brief(world)), "--plan", str(world.plan)]) == 2
    assert capsys.readouterr().err == TWO; untouched(world)


def test_text_with_brief_is_refused(world, capsys):
    assert io.main(["send", "W1", "--text", "x", "--brief", str(brief(world))]) == 2
    assert capsys.readouterr().err == TWO; untouched(world)


def test_all_three_is_refused(world, capsys):
    assert io.main(["send", "W1", "T3", "--text", "x", "--brief", str(brief(world)), "--plan", str(world.plan)]) == 2
    assert capsys.readouterr().err == TWO; untouched(world)


def test_empty_text_counts(world, capsys):
    assert io.main(["send", "W1", "T3", "--text", "", "--plan", str(world.plan)]) == 2
    assert capsys.readouterr().err == TWO; untouched(world)


def test_refusal_comes_before_the_brief_check(world, capsys):
    assert io.main(["send", "W1", "T3", "--brief", "missing.md", "--plan", str(world.plan)]) == 2
    assert capsys.readouterr().err == TWO


def test_single_kinds_still_send(world, capsys):
    assert io.main(["send", "W1", "T3", "--plan", str(world.plan)]) == 0
    assert "W1 T3 sent" in capsys.readouterr().out
    assert io.main(["send", "W2", "--text", "hi"]) == 0
    fl = json.loads((world.sd / "fleet.json").read_text()); fl["workers"]["W1"]["state"] = "ready"; fl["workers"]["W1"]["task"] = None
    (world.sd / "fleet.json").write_text(json.dumps(fl))
    pl = json.loads((world.sd / "pool.json").read_text()); pl["agents"][0]["busy"] = False
    (world.sd / "pool.json").write_text(json.dumps(pl))
    assert io.main(["send", "W1", "--brief", str(brief(world))]) == 0


def test_no_kind_keeps_its_error(world, capsys):
    assert io.main(["send", "W1"]) == 2
    assert capsys.readouterr().err == "error: send needs task ids, --text or --brief\n"
