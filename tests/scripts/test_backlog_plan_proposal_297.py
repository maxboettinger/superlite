import json
import sys

from test_backlog_cli import bk, cli, load, BATCH  # noqa: F401  bk is the CLI fixture
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402

Q = {"questions": [{"question": "Which store?", "header": "Dependencies!",
                    "options": [{"label": "A (Recommended)", "description": "a"}, {"label": "B", "description": "b"}]}]}
OK = {"by": "AskUserQuestion", "time": "2026-11-08T10:00:00Z"}


def write(bk, obj, name="fixed.json"):
    f = bk.root / name
    f.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return str(f)


def test_a_proposal_file_is_applied_without_a_worker(bk, capsys):
    bs.update(bs.path(bk.root), lambda d: d.update(approved_ship=OK))
    f = write(bk, {"batches": [BATCH]})
    rc, out = cli(capsys, "plan", "--proposal", f)
    d = load(bk)
    assert rc == 0 and "B1 | #1 #2 | planned" in out
    assert bk.calls == [] and not (bk.sd / "briefs" / "triage.md").exists()
    assert d["repo"] == "o/r" and d["approved_ship"] is None and [b["id"] for b in d["batches"]] == ["B1"]
    assert d["titles"] == {"1": "One", "2": "Two"} and d["outside"] == [{"number": 3, "title": "Three", "author": "eve"}]


def test_a_triage_report_with_a_json_block_is_read(bk, capsys):
    f = write(bk, "Status: DONE\n```json\n" + json.dumps({"status": "DONE", "batches": [BATCH]}) + "\n```\n", "triage.md")
    assert cli(capsys, "plan", "--proposal", f)[0] == 0 and load(bk)["batches"][0]["issues"] == [1, 2]


def test_texts_in_the_file_are_cut_and_named(bk, capsys):
    f = write(bk, {"batches": [{**BATCH, "decisions": [Q]}]})
    rc, out = cli(capsys, "plan", "--proposal", f)
    assert rc == 0 and out.endswith('shortened: "Which store?" header: 13 -> 12 characters\n')
    assert load(bk)["batches"][0]["decisions"][0]["questions"][0]["header"] == "Dependencies"


def test_a_kept_proposal_applies_after_a_repair(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1, 9], "decisions": [Q]}]
    rc, out = cli(capsys, "plan")
    kept = bk.sd / "backlog-proposal.json"
    assert rc == 3 and "B1: unknown issue #9" in out and f"proposal kept: {kept}" in out
    p = json.loads(kept.read_text())
    p["batches"][0]["issues"] = [1]
    kept.write_text(json.dumps(p))
    rc, out = cli(capsys, "plan", "--proposal", str(kept))
    assert rc == 0 and "B1 | #1 | planned" in out and "shortened" not in out


def test_a_rejected_file_is_kept_and_names_no_worker(bk, capsys):
    f = write(bk, {"status": "DONE", "summary": "s", "batches": [{**BATCH, "issues": [9]}]})
    rc, out = cli(capsys, "plan", "--proposal", f)
    kept = bk.sd / "backlog-proposal.json"
    assert (rc, out) == (3, f"BLOCKED: proposal rejected\nB1: unknown issue #9\nproposal kept: {kept}\n")
    assert json.loads(kept.read_text())["batches"][0]["issues"] == [9] and load(bk)["batches"] == []


def test_unreadable_or_shapeless_files_are_refused_before_gh(bk, capsys):
    missing = str(bk.root / "nope.json")
    rc, out = cli(capsys, "plan", "--proposal", missing)
    assert rc == 2 and out.startswith(f"BLOCKED: proposal {missing} unreadable: ") and out.count("\n") == 1
    raw = bk.root / "bin.json"
    raw.write_bytes(b"\xff\xfe\x00")
    rc, out = cli(capsys, "plan", "--proposal", str(raw))
    assert rc == 2 and out.startswith(f"BLOCKED: proposal {raw} unreadable: ")
    for body in ("[1, 2]", "no json here", '```json\n{"x": 1}\n```\n', "[" * 100000 + "]" * 100000):
        f = write(bk, body, "bad.txt")
        assert cli(capsys, "plan", "--proposal", f) == (2, f"BLOCKED: proposal {f} holds no JSON object\n")
    assert bk.gh == [] and bk.calls == []


def test_open_batches_refuse_before_the_file_is_read(bk, capsys):
    f = write(bk, {"batches": [BATCH]})
    assert cli(capsys, "plan", "--proposal", f)[0] == 0
    assert cli(capsys, "plan", "--proposal", str(bk.root / "nope.json")) == (2, "BLOCKED: backlog has open batches (B1 planned)\n")
    assert cli(capsys, "plan", "--reset", "--proposal", f)[0] == 0 and [b["id"] for b in load(bk)["batches"]] == ["B1"]


def test_clashing_batches_merge_and_renumber_after_shipped_ones(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "shipped"}))
    f = write(bk, {"batches": [{**BATCH, "issues": [1]}, {**BATCH, "id": "B2", "topic": "second", "issues": [2]}]})
    assert cli(capsys, "plan", "--proposal", f)[0] == 0
    assert [(b["id"], b["state"], b["issues"]) for b in load(bk)["batches"]] == [("B1", "shipped", [1, 2]), ("B2", "planned", [1, 2])]


def test_deeply_nested_and_non_dict_batches_are_rejected_not_crashed(bk, capsys):
    deep = '{"batches": [1, "x", null], "x": ' + "[" * 900 + "]" * 900 + "}"
    rc, out = cli(capsys, "plan", "--proposal", write(bk, deep))
    assert rc == 3 and out.startswith("BLOCKED: proposal rejected\nbatch 1: not an object") and "triage worker" not in out
    rc, out = cli(capsys, "plan", "--proposal", write(bk, {"foo": 1}))
    assert rc == 3 and "not an object with batches" in out


def test_a_batch_started_meanwhile_is_not_overwritten_and_names_no_triage(bk, capsys, monkeypatch):
    import backlog as bl
    f = write(bk, {"batches": [BATCH]})
    real = bl._gh

    def gh(*a, **k):
        r = real(*a, **k)
        bs.update(bs.path(bk.root), lambda d: d["batches"].append({**BATCH, "id": "B9", "state": "running"}))
        return r
    monkeypatch.setattr(bl, "_gh", gh)
    rc, out = cli(capsys, "plan", "--proposal", f)
    assert rc == 3 and "changed while the proposal was checked" in out and "triage" not in out


def test_a_bom_prefixed_proposal_is_applied(bk, capsys):
    f = bk.root / "bom.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps({"batches": [BATCH]}).encode())
    rc, out = cli(capsys, "plan", "--proposal", str(f))
    assert rc == 0 and "B1 | #1 #2 | planned" in out and bk.calls == []


def test_an_empty_proposal_path_is_unreadable_not_a_triage(bk, capsys):
    rc, out = cli(capsys, "plan", "--proposal", "")
    assert rc == 2 and out.startswith("BLOCKED: proposal  unreadable: ")
    assert bk.calls == [] and bk.gh == []
