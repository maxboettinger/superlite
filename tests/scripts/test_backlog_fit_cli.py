import json, sys
from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401  bk is the CLI fixture
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

REC = " (Recommended)"
LONG = {"questions": [{"question": "Which store?", "header": "Dependencies!",
                       "options": [{"label": "x" * 72 + REC, "description": "a"}, {"label": "Drop", "description": "b"}]}]}
NOTES = ['"Which store?" header: 13 -> 12 characters', '"Which store?" option 1 label: 86 -> 60 characters']

def test_plan_shortens_a_long_header_and_label_and_says_so(bk, capsys):
    bk.batches = [{**BATCH, "decisions": [LONG]}]
    rc, out = cli(capsys, "plan")
    e = load(bk)["batches"][0]["decisions"][0]["questions"][0]
    assert rc == 0 and "B1 | #1 #2 | planned" in out
    assert e["header"] == "Dependencies" and e["options"][0]["label"] == "x" * 46 + REC
    assert out.endswith("".join(f"shortened: {n}\n" for n in NOTES))

def test_a_rejected_proposal_is_kept_shortened_and_names_the_cuts(bk, capsys):
    bk.batches = [{**BATCH, "issues": [9], "decisions": [LONG]}]
    rc, out = cli(capsys, "plan")
    kept = json.loads((bk.sd / "backlog-proposal.json").read_text())
    assert rc == 3 and "BLOCKED: proposal rejected" in out and "B1: unknown issue #9" in out
    assert out.endswith("".join(f"shortened: {n}\n" for n in NOTES))
    assert kept["batches"][0]["decisions"][0]["questions"][0]["header"] == "Dependencies"

def test_more_than_five_cuts_print_five_and_a_count(bk, monkeypatch, capsys):
    notes = [f'"Q" option {n} description: 201 -> 200 characters' for n in range(1, 8)]
    monkeypatch.setattr(bc, "fit_proposal", lambda obj: list(notes))
    rc, out = cli(capsys, "plan")
    assert rc == 0 and out.count('shortened: "Q"') == 5 and out.endswith("shortened: 2 more\n")

def test_nothing_to_cut_prints_no_shortened_line(bk, capsys):
    rc, out = cli(capsys, "plan")
    assert rc == 0 and "shortened" not in out
