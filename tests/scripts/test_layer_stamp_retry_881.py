# tests/scripts/test_layer_stamp_retry_881.py
"""#881: an evals stamp drops a case its newer evals.sh retry turned green; a stale, red, missing or bad retry keeps it red."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_test_layers import cli, real_store, repo, store_file, tl  # noqa: E402,F401  (repo is a fixture)


def result(*cases, threshold=1):
    return json.dumps({"suite": {"threshold": threshold},
                       "cases": [{"name": n, "aggregates": {"score": s}} for n, s in cases]})


def results_dir(root: Path) -> Path:
    out = root / "evals" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "last.json").write_text(result(("a", 0.5), ("b", 0.5), ("c", 1)))
    return out


def test_retry_green_case_is_not_red_881(tmp_path):
    out = results_dir(tmp_path)
    (out / "retry-a.json").write_text(result(("a", 1)))
    assert tl.evals_red(out) == ["b"]


def test_retry_still_red_keeps_the_case_881(tmp_path):
    out = results_dir(tmp_path)
    (out / "retry-a.json").write_text(result(("a", 0.5)))
    assert tl.evals_red(out) == ["a", "b"]


def test_retry_older_than_last_json_is_ignored_881(tmp_path):
    out = results_dir(tmp_path)
    retry = out / "retry-a.json"
    retry.write_text(result(("a", 1)))
    t = (out / "last.json").stat().st_mtime - 60
    os.utime(retry, (t, t))
    assert tl.evals_red(out) == ["a", "b"]


def test_retry_naming_another_case_or_bad_json_keeps_red_881(tmp_path):
    out = results_dir(tmp_path)
    (out / "retry-a.json").write_text(result(("z", 1)))
    (out / "retry-b.json").write_text("{not json")
    assert tl.evals_red(out) == ["a", "b"]


def test_unsafe_case_name_never_reads_a_retry_881(tmp_path):
    out = tmp_path / "evals" / "results"
    (out / "retry-..").mkdir(parents=True)
    (out / "last.json").write_text(result(("../x", 0.5)))
    (out / "retry-.." / "x.json").write_text(result(("../x", 1)))
    assert tl.evals_red(out) == ["../x"]


def test_missing_last_json_has_no_red_881(tmp_path):
    assert tl.evals_red(tmp_path / "evals" / "results") == []


def test_stamp_evals_records_only_what_the_retry_left_red_881(repo):
    out = results_dir(repo)
    (out / "retry-a.json").write_text(result(("a", 1)))
    r = cli(repo, "stamp", "evals", "--ruling", "judge flake")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "evals: stamped (red: b)"
    rec = real_store.stamp_of(store_file(repo), "evals", tl.layer_hash("evals", repo))
    assert rec["red"] == ["b"]


def test_explicit_red_still_wins_881(repo):
    out = results_dir(repo)
    (out / "retry-a.json").write_text(result(("a", 1)))
    assert cli(repo, "stamp", "evals", "--ruling", "r", "--red", "a").stdout.strip() == "evals: stamped (red: a)"
