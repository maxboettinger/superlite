"""reviewer_eval_cli.py with gh, review and grade faked; git runs for real in tmp repos."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))
import reviewer_eval_cli as cli  # noqa: E402
import reviewer_eval_live as live  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(h))
    return h


def git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=n", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=True).stdout.strip()


def test_set_dir_under_the_superlite_home_and_refuses_bad_names(home, monkeypatch):
    assert cli.set_dir("own") == home / "reviewer-eval" / "own"
    for bad in ("../x", "a/b", "", ".", ".."):
        with pytest.raises(ValueError):
            cli.set_dir(bad)
    monkeypatch.delenv("SUPERLITE_HOME")
    assert cli.set_dir("own") == Path.home() / ".superlite" / "reviewer-eval" / "own"


def test_make_case_appends_and_refuses_a_duplicate(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "f").write_text("1")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "one")
    first = git(repo, "rev-parse", "HEAD")
    (repo / "f").write_text("2")
    git(repo, "commit", "-qam", "two")
    merge = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(cli, "_gh", lambda r, pr: {"mergeCommit": {"oid": merge}, "title": "T", "body": "B"})
    args = ["make-case", "--repo", str(repo), "--pr", "7", "--set", "own"]
    assert cli.main(args) == 0
    cases = json.loads((cli.set_dir("own") / "cases.json").read_text())
    assert cases == [{"id": "pr-7", "repo": str(repo), "base": first, "merge": merge, "title": "T", "body": "B"}]
    assert cli.main(args) == 2 and "pr-7 already in the set" in capsys.readouterr().err
    monkeypatch.setattr(cli, "_gh", lambda r, pr: {"mergeCommit": None, "title": "T", "body": "B"})
    assert cli.main(["make-case", "--repo", str(repo), "--pr", "8", "--set", "own"]) == 2


def write_cases(n=2, name="own"):
    d = cli.set_dir(name)
    d.mkdir(parents=True)
    cases = [{"id": f"c{i}", "repo": "/r", "base": "b", "merge": "m", "title": "t", "body": "x"} for i in range(n)]
    (d / "cases.json").write_text(json.dumps(cases))
    return d


def fake_live(monkeypatch, seen=None, fail=()):
    def review(case, variant, work):
        if seen is not None:
            seen.append((case["id"], variant))
        if case["id"] in fail:
            raise live.LiveError("boom")
        return {"findings": [{"fp": "f1", "file": "a", "line": 1, "problem": "p", "quote": "q"}], "unverified": 0, "cost_usd": 1.0, "seconds": 1.0}

    monkeypatch.setattr(live, "review", review)
    monkeypatch.setattr(live, "grade", lambda case, pooled, model="opus": {"f1": {"grade": "real", "serious": True}})


def test_run_default_variant_comes_from_the_agent_file(monkeypatch):
    write_cases(1)
    seen = []
    fake_live(monkeypatch, seen)
    assert cli.main(["run", "--set", "own"]) == 0
    text = (ROOT / "agents" / "final-reviewer.md").read_text()
    model = re.search(r"^model:\s*(\S+)", text, re.M).group(1)
    effort = re.search(r"^effort:\s*(\S+)", text, re.M).group(1)
    assert seen == [("c0", {"name": "current", "model": model, "effort": effort})]


def test_run_writes_results_and_prints_the_table(monkeypatch, capsys, home):
    d = write_cases(2)
    fake_live(monkeypatch)
    assert cli.main(["run", "--set", "own", "--variant", "a=sonnet:low", "--variant", "b=opus:high"]) == 0
    files = list((d / "results").glob("*.json"))
    assert len(files) == 1 and re.fullmatch(r"\d{8}T\d{6}Z\.json", files[0].name)
    data = json.loads(files[0].read_text())
    assert len(data["rows"]) == 2 and set(data["summary"]) == {"a", "b"}
    out = capsys.readouterr().out.rstrip("\n").splitlines()
    assert out[-3].split()[0] == "variant" and out[-2].split()[0] == "a" and out[-1].split()[0] == "b"
    assert not (ROOT / "reviewer-eval").exists()


def test_run_limit_and_a_failing_case(monkeypatch):
    d = write_cases(3)
    seen = []
    fake_live(monkeypatch, seen)
    assert cli.main(["run", "--set", "own", "--limit", "1"]) == 0
    assert [s[0] for s in seen] == ["c0"]
    seen.clear()
    fake_live(monkeypatch, seen, fail=("c1",))
    assert cli.main(["run", "--set", "own"]) == 1
    assert [s[0] for s in seen] == ["c0", "c1", "c2"]
    data = json.loads(sorted((d / "results").glob("*.json"))[-1].read_text())
    assert [f["case"] for f in data["failed"]] == ["c1"] and len(data["rows"]) == 2


def test_report_prints_the_newest_result(capsys):
    d = write_cases(1)
    assert cli.main(["report", "--set", "own"]) == 2 and "no results in own" in capsys.readouterr().err
    (d / "results").mkdir()
    row = {"real": 1, "serious": 0, "nit": 0, "wrong": 0, "ungraded": 0, "unverified": 0, "recall": 1.0, "precision": 1.0, "cost_usd": 1.0}
    (d / "results" / "20260101T000000Z.json").write_text(json.dumps({"summary": {"old": row}}))
    (d / "results" / "20260102T000000Z.json").write_text(json.dumps({"summary": {"new": row}}))
    assert cli.main(["report", "--set", "own"]) == 0
    out = capsys.readouterr().out
    assert "new" in out and "old" not in out


def test_usage_errors_exit_2(monkeypatch):
    assert cli.main(["run", "--set", "nope"]) == 2
    write_cases(1)
    assert cli.main(["run", "--set", "own", "--variant", "sonnet"]) == 2
    assert cli.main(["run", "--set", "../x"]) == 2
    assert cli.main([]) == 2


def test_non_positive_limit_is_a_usage_error(monkeypatch):
    write_cases(3)
    seen = []
    fake_live(monkeypatch, seen)
    assert cli.main(["run", "--set", "own", "--limit", "-1"]) == 2
    assert cli.main(["run", "--set", "own", "--limit", "0"]) == 2
    assert seen == []


def test_experiments_doc_has_the_section():
    text = (ROOT / "docs" / "experiments.md").read_text(encoding="utf-8")
    assert "## Reviewer eval" in text
    section = text.split("## Reviewer eval", 1)[1].split("\n## ", 1)[0]
    for cmd in ("make-case", "run", "report"):
        assert cmd in section
