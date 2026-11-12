"""B126 (#586): decide takes the one answer rule, unskip, reset, full help, parked-only next line, ship-done offer."""
import json

import pytest

from test_backlog_cli import bk, cli, load, BATCH, bs, bl  # noqa: F401  bk is the CLI fixture
import backlog_undo  # noqa: E402
from backlog_fixtures import Q, batch


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: [])


def seed(bk, **kw):
    bs.update(bs.path(bk.root), lambda d: d.update(kw))


def answers_file(tmp_path, answers):
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": answers, "by": "user"}))
    return str(f)


def test_help_lists_every_subcommand(capsys):
    with pytest.raises(SystemExit) as e:
        bl.main(["--help"])
    out = capsys.readouterr().out
    assert e.value.code == 0
    for name in ("status", "plan", "decide", "start", "wait", "answer", "tell", "ship", "skip", "unskip", "park", "reset"):
        assert name in out


def test_unskip_cli(bk, capsys, monkeypatch):
    seed(bk, skipped=[2])
    rc, out = cli(capsys, "unskip", "2")
    assert rc == 0 and out.startswith("unskipped #2: ") and load(bk)["skipped"] == []
    assert cli(capsys, "unskip", "2") == (2, "refused: #2 is not skipped\n")
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W3")
    assert cli(capsys, "unskip", "2") == (2, "refused: sl backlog unskip runs only in the main session\n")


def test_reset_cli_passes_discard(bk, capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(backlog_undo, "reset_batch", lambda root, bid, discard=False: seen.append((root, bid, discard)) or (3, ["one", "two"]))
    assert cli(capsys, "reset", "B1", "--discard") == (3, "one\ntwo\n")
    assert cli(capsys, "reset", "B1")[0] == 3
    assert seen == [(bk.root, "B1", True), (bk.root, "B1", False)]


def test_skipped_pin_names_unskip(bk, capsys):
    seed(bk, skipped=[2, "PIX-1"])
    assert cli(capsys, "plan", "--issues", "1,2") == (2, "BLOCKED: --issues: #2 is skipped; sl backlog unskip 2 takes it back\n")
    assert cli(capsys, "plan", "--issues", "pix-1") == (2, "BLOCKED: --issues: PIX-1 is skipped; sl backlog unskip PIX-1 takes it back\n")


def test_status_parked_only_next_line(bk, capsys):
    seed(bk, batches=[batch("B60", ["a.py"], "parked"), batch("B59", ["b.py"], "shipped")])
    rc, out = cli(capsys, "status")
    assert rc == 0 and out.splitlines()[-1] == bl.parked_next(load(bk))
    assert out.splitlines()[-1].startswith("next: sl backlog start B60 resumes the parked batch")


def test_parked_next_values():
    p = lambda *s: {"batches": [{"id": f"B{i}", "state": x} for i, x in zip((60, 61, 62), s)]}
    assert bl.parked_next(p("parked", "shipped")) == ("next: sl backlog start B60 resumes the parked batch, or sl backlog plan --reset "
                                                      "drops it and plans every open issue again")
    assert bl.parked_next(p("parked", "parked")) == ("next: sl backlog start B60 B61 resumes the parked batches, or sl backlog plan --reset "
                                                     "drops them and plans every open issue again")
    for s in ("planned", "running", "needs_decision"):
        assert bl.parked_next(p("parked", s)) is None
    assert bl.parked_next(p("shipped")) is None and bl.parked_next({"batches": []}) is None


def test_decide_label_plus_note(bk, capsys, tmp_path):
    bk.batches = [{**BATCH, "decisions": [Q["questions"][0]]}]
    cli(capsys, "plan")
    q = "B1: Keep the v1 API?"
    rc, out = cli(capsys, "decide", "--file", answers_file(tmp_path, {q: {"label": "Drop", "note": "log it"}}))
    assert rc == 0 and out.startswith("recorded 1 answers")
    assert load(bk)["batches"][0]["answers"]["Keep the v1 API?"] == "Drop; note: log it"


def test_decide_free_text_still_accepted(bk, capsys, tmp_path):
    bk.batches = [{**BATCH, "decisions": [Q["questions"][0]]}]
    cli(capsys, "plan")
    q = "B1: Keep the v1 API?"
    assert cli(capsys, "decide", "--file", answers_file(tmp_path, {q: "Drop, and log it"}))[0] == 0
    assert load(bk)["batches"][0]["answers"]["Keep the v1 API?"] == "Drop, and log it"


def test_decide_ship_refuses_note_and_free_text(bk, capsys, tmp_path):
    cli(capsys, "plan")
    rc, out = cli(capsys, "decide", "--file", answers_file(tmp_path, {bs.SHIP_Q: "Yes please"}))
    assert rc == 2
    assert out == ("BLOCKED: bad answer for Approve that every batch lead ships its own batch (rebase, v"
                   ": answer must be one of: Approve shipping, Not yet\n")
    assert load(bk)["approved_ship"] is None
    rc, out = cli(capsys, "decide", "--file", answers_file(tmp_path, {bs.SHIP_Q: {"label": "Approve shipping", "note": "x"}}))
    assert rc == 2 and "takes only its label" in out and load(bk)["approved_ship"] is None


def test_decide_bad_answer_question_has_no_control_chars(bk, capsys, tmp_path, monkeypatch):
    q = {"question": "Keep\x1b[2J\nthe API?", "options": [{"label": "Keep"}, {"label": "Drop"}]}
    cli(capsys, "plan")
    monkeypatch.setattr(bs, "open_questions", lambda d: [q])
    rc, out = cli(capsys, "decide", "--file", answers_file(tmp_path, {q["question"]: {"label": "Later", "note": ""}}))
    assert rc == 2 and out.startswith("BLOCKED: bad answer for Keep?[2J?the API?: ") and out.count("\n") == 1 and "\x1b" not in out


def test_decide_unknown_question_passes_unchanged(bk, capsys, tmp_path):
    cli(capsys, "plan")
    assert cli(capsys, "decide", "--file", answers_file(tmp_path, {"Nope?": "x"})) == (2, "no open question: Nope?\n")


def test_plan_offers_ship_done(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: ["a1b2c3d\tFix #1 (#20)"])
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, out = cli(capsys, "plan", "--issues", "1")
    assert rc == 0
    assert ("offer: B1 holds only #1, named by merged PR #20: sl backlog ship B1 done --pr 20 records it as shipped "
            "(no lead, no worktree)") in out.splitlines()


def test_offer_lines():
    ship = lambda b, i, pr: f"offer: {b} holds only {i}, named by merged PR #{pr}: sl backlog ship {b} done --pr {pr} records it as shipped (no lead, no worktree)"
    assert bl.offer_lines([{"id": "B2", "issues": [6]}], {6: "PR #20"}) == [ship("B2", "#6", 20)]
    assert bl.offer_lines([{"id": "B2", "issues": [6, 7]}], {6: "PR #20", 7: "commit a1b2c3d"}) == []
    assert bl.offer_lines([{"id": "B2", "issues": [6, 7]}], {6: "PR #20", 7: "PR #21"}) == []
    assert bl.offer_lines([{"id": "B2", "issues": [6, 7]}], {6: "PR #20"}) == []
    assert bl.offer_lines([{"id": "B3", "issues": ["PIX-3", "PIX-4"]}], {"PIX-3": "PR #9", "PIX-4": "PR #9"}) == [ship("B3", "PIX-3 PIX-4", 9)]
    assert bl.offer_lines([{"id": "B4", "issues": []}], {}) == []
