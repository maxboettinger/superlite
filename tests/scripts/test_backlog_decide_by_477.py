import json, sys, types
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401


def test_decide_approve_ship_prompt(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(bl, "_now", lambda: "T")
    assert cli(capsys, "decide", "--approve-ship", "--source", "prompt")[0] == 2
    cli(capsys, "plan")
    assert cli(capsys, "decide", "--approve-ship") == (2, "BLOCKED: --approve-ship needs --source prompt\n")
    assert cli(capsys, "decide", "--approve-ship", "--source", "user") == (2, "refused: --source: only prompt (an AskUserQuestion answer goes through decide --file)\n")
    assert cli(capsys, "decide", "--approve-ship", "--source", "prompt") == (0, "ship approved (prompt T): every batch of this plan round may ship\n")
    assert load(bk)["approved_ship"] == {"by": "prompt", "time": "T"}


def test_decide_file_by_main(bk, capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    cli(capsys, "plan")
    q = json.loads(cli(capsys, "decide", "--print")[1])["questions"][0]["question"]
    def go(obj):
        f = tmp_path / "a.json"; f.write_text(json.dumps(obj))
        return cli(capsys, "decide", "--file", str(f))
    rc, out = go({"answers": {bs.SHIP_Q: "Approve shipping"}, "by": "main"})
    assert rc == 2 and bs.SHIP_MAIN in out
    assert go({"answers": {q: "Skip"}, "by": {q: "main"}}) == (0, "recorded 1 answers (1 ruled by main), 1 open\n")
    assert go({"answers": {q: "Skip"}, "by": "bot"}) == (2, 'BLOCKED: by: "user", "main" or a {question: "user"|"main"} map\n')


def test_tell_is_routed(monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, "backlog_run", types.SimpleNamespace(main=lambda argv: seen.append(list(argv)) or 0))
    assert bl.main(["tell", "B1", "--text", "x"]) == 0
    assert seen == [["tell", "B1", "--text", "x"]]
