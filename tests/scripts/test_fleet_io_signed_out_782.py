import json
from test_fleet_io import io, world  # noqa: F401  (world is a fixture)

MARKS = ("Select login method:", "Paste code here if prompted", "Browser didn't open? Use the url below to sign in", "Opening browser to sign in")


def fake_sign_in(screen):
    """Follows accounts.sign_in_screen: a line that starts with a mark."""
    return any(ln.strip(" \t│❯>●").startswith(MARKS) for ln in (screen or "").splitlines())


def busy(world, monkeypatch, capsys, account="a1"):
    monkeypatch.setattr(io.accounts, "sign_in_screen", fake_sign_in, raising=False)
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    p = world.sd / "fleet.json"; data = json.loads(p.read_text())
    data["workers"]["W1"].update(task="R1", account=account); p.write_text(json.dumps(data))
    capsys.readouterr()


def prompts(world):
    return [c for c in world.fh.calls if c[0] in ("prompt", "send_keys")]


def test_wait_sign_in_screen_is_blocked_not_done(world, monkeypatch, capsys):
    busy(world, monkeypatch, capsys)
    before = len(prompts(world))
    world.fh.states = [{"sl-proj-w1": "idle"}]
    world.fh.screen = "Select login method:\nStatus: DONE\n"
    out = io.wait(world.sd, ["W1"], 60000)
    text = capsys.readouterr().out
    assert [r["status"] for r in out] == ["BLOCKED-UI"]
    assert "W1 R1 BLOCKED-UI" in text and "signed out: account a1 shows the Claude Code sign-in screen; sign in there, then respawn" in text
    assert "W1 R1 DONE" not in text
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "blocked"
    assert len(prompts(world)) == before


def test_wait_blocked_state_names_signed_out(world, monkeypatch, capsys):
    busy(world, monkeypatch, capsys)
    world.fh.states = [{"sl-proj-w1": "blocked"}]
    world.fh.screen = "Select login method:\n"
    out = io.wait(world.sd, ["W1"], 60000)
    assert [r["status"] for r in out] == ["BLOCKED-UI"]
    assert "signed out: account a1" in capsys.readouterr().out


def test_wait_plain_screen_unchanged(world, monkeypatch, capsys):
    busy(world, monkeypatch, capsys)
    world.fh.states = [{"sl-proj-w1": "idle"}]
    world.fh.screen = "Status: DONE\n"
    out = io.wait(world.sd, ["W1"], 60000)
    assert [(r["status"], r["source"]) for r in out] == [("DONE", "screen")]
    assert "signed out" not in capsys.readouterr().out


def test_blocked_without_sign_in_unchanged(world, monkeypatch, capsys):
    busy(world, monkeypatch, capsys)
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    world.fh.screen = "Do you trust the files in this folder?\n"
    r = io._blocked(world.sd, "W1", w)
    text = capsys.readouterr().out
    assert r["status"] == "BLOCKED-UI" and "signed out" not in text
    assert text.splitlines()[0] == f"W1 R1 BLOCKED-UI {world.sd}/fleet/screens/W1.txt"
