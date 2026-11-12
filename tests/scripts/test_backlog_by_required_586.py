"""An answers file must name who answered (#586)."""
import json
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
import backlog_checks as bc


def test_answer_by_examples():
    assert bc.answer_by({"answers": {"A?": "x"}}, {"A?": "x"}) == ({}, bc.BY_MISSING)
    assert bc.answer_by("nope", {"A?": "x"}) == ({}, bc.BY_MISSING)
    assert bc.answer_by({"answers": {"A?": "x", "B?": "y"}, "by": {"A?": "main"}}, {"A?": "x", "B?": "y"}) == ({}, "by: the map names no one for B?")
    assert bc.answer_by({"by": "user"}, {"A?": "x"}) == ({"A?": "user"}, "")
    assert bc.answer_by({"by": {"A?": "main"}}, {"A?": "x"}) == ({"A?": "main"}, "")
    assert bc.answer_by({"by": "bot"}, {"A?": "x"}) == ({}, bc.BY_ERR)


def test_partial_map_refused():
    long = "Q" * 80 + "\x1b"
    err = bc.answer_by({"by": {"A?": "main"}}, {"A?": "x", long: "y"})[1]
    assert err == "by: the map names no one for " + "Q" * 60
    err = bc.answer_by({"by": {"A?": "main"}}, {"A?": "x", "a\x1bb": "y"})[1]
    assert err == "by: the map names no one for a?b"


def test_decide_refuses_missing_by(bk, capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    cli(capsys, "plan")
    q = json.loads(cli(capsys, "decide", "--print")[1])["questions"][0]["question"]
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {q: "Skip"}}))
    assert cli(capsys, "decide", "--file", str(f)) == (2, "BLOCKED: " + bc.BY_MISSING + "\n")
    assert all(not b.get("answers") for b in load(bk)["batches"])


def test_decide_counts_user_answers(bk, capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    cli(capsys, "plan")
    q = json.loads(cli(capsys, "decide", "--print")[1])["questions"][0]["question"]
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {q: "Skip"}, "by": "main"}))
    assert cli(capsys, "decide", "--file", str(f))[1].startswith("recorded 1 answers (1 ruled by main), ")
    f.write_text(json.dumps({"answers": {bs.SHIP_Q: "Approve shipping"}, "by": {bs.SHIP_Q: "user"}}))
    assert cli(capsys, "decide", "--file", str(f))[1] == "recorded 1 answers (1 as the user's), 0 open\n"
