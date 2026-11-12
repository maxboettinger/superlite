"""#626: a stamp records its ruling, time and red cases; status shows it as stamped; a green run clears it."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_test_layers import cli, real_store, repo, store_file, tl  # noqa: E402,F401  (repo is a fixture)


def evals_line(root):
    return next(ln for ln in cli(root, "status").stdout.splitlines() if ln.startswith("evals "))


def record(root, layer="evals"):
    return real_store.stamp_of(store_file(root), layer, tl.layer_hash(layer, root))


def test_stamp_records_ruling_time_and_red_626(repo):
    r = cli(repo, "stamp", "evals", "--ruling", "judge flake", "--red", "brainstorm-coverage", "debug-flow")
    assert r.returncode == 0, r.stderr
    rec = record(repo)
    assert rec["ruling"] == "judge flake"
    assert rec["red"] == ["brainstorm-coverage", "debug-flow"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", rec["at"])
    assert r.stdout.strip() == "evals: stamped (red: brainstorm-coverage, debug-flow)"


def test_status_shows_stamped_not_green_626(repo):
    cli(repo, "stamp", "evals", "--ruling", "judge flake", "--red", "brainstorm-coverage")
    line = evals_line(repo)
    assert line.startswith("evals stamped " + tl.layer_hash("evals", repo)[:12] + " at ")
    assert line.endswith(", red: brainstorm-coverage, ruling: judge flake")
    assert "evals" not in cli(repo, "check").stdout


def test_green_run_clears_the_stamp_626(repo):
    cli(repo, "stamp", "evals", "--ruling", "r", "--red", "x")
    assert cli(repo, "run", "evals", "--command-override", "evals=true").returncode == 0
    assert evals_line(repo).startswith("evals green ")
    assert record(repo) is None


def test_evals_stamp_reads_red_cases_from_last_json_626(repo):
    out = repo / "evals" / "results"
    out.mkdir(parents=True)
    (out / "last.json").write_text(json.dumps({"suite": {"threshold": 1}, "cases": [
        {"name": "a", "aggregates": {"score": 0.5}}, {"name": "b", "aggregates": {"score": 1}},
        {"name": "c", "aggregates": {}}]}))
    assert cli(repo, "stamp", "evals", "--ruling", "r").returncode == 0
    assert record(repo)["red"] == ["a", "c"]


def test_red_cases_reads_nothing_from_a_missing_or_bad_file_626(tmp_path):
    assert tl.red_cases(tmp_path / "missing.json") == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert tl.red_cases(bad) == []
    bad.write_text(json.dumps({"cases": [{"name": "n", "aggregates": {"score": 0.9}}]}))
    assert tl.red_cases(bad) == ["n"]


def test_non_evals_stamp_has_no_red_cases_626(repo):
    assert cli(repo, "stamp", "tui", "--ruling", "no tmux").stdout.strip() == "tui: stamped (red: none)"
    rec = record(repo, "tui")
    assert rec["red"] == [] and rec["ruling"] == "no tmux"


def test_ruling_newlines_keep_status_one_line_626(repo):
    cli(repo, "stamp", "evals", "--ruling", "line one\nline two")
    assert evals_line(repo).endswith("ruling: line one line two")


def test_store_keeps_a_stamp_until_its_digest_runs_green_626(tmp_path):
    s = tmp_path / "store.json"
    rec = {"ruling": "r", "at": "2026-11-12T09:00:00Z", "red": ["x"]}
    real_store.record_green(s, "evals", "d1", {"a": "1"}, stamp=rec)
    real_store.record_green(s, "evals", "d2", {"a": "2"})
    assert real_store.stamp_of(s, "evals", "d1") == rec
    assert real_store.stamp_of(s, "evals", "d2") is None
    real_store.record_green(s, "evals", "d1", {"a": "1"})
    assert real_store.stamp_of(s, "evals", "d1") is None
    assert real_store.is_green(s, "evals", "d1")


def test_stamp_dropped_with_its_green_hash_626(tmp_path, monkeypatch):
    s = tmp_path / "store.json"
    monkeypatch.setattr(real_store, "KEEP", 2)
    real_store.record_green(s, "evals", "d1", {}, stamp={"ruling": "r", "at": "t", "red": []})
    real_store.record_green(s, "evals", "d2", {})
    real_store.record_green(s, "evals", "d3", {})
    assert not real_store.is_green(s, "evals", "d1")
    assert "d1" not in real_store.layer_entry(s, "evals").get("stamps", {})


def test_red_cases_survives_corrupt_types_626(tmp_path):
    f = tmp_path / "last.json"
    f.write_text(json.dumps({"suite": {"threshold": "high"}, "cases": [{"name": "a", "aggregates": {"score": 0.5}}, {"name": "b", "aggregates": {"score": 1.0}}]}))
    assert tl.red_cases(f) == ["a"]
    f.write_text(json.dumps({"suite": {"threshold": True}, "cases": [{"name": "a", "aggregates": {"score": 0.5}}]}))
    assert tl.red_cases(f) == ["a"]
    f.write_text("[]")
    assert tl.red_cases(f) == []
    f.write_text(json.dumps({"cases": [{"name": "s", "aggregates": {"score": "1"}}, {"name": "t", "aggregates": {"score": True}}, {"name": "u", "aggregates": []}]}))
    assert tl.red_cases(f) == ["s", "t", "u"]
