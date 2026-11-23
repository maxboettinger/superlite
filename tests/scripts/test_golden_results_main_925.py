import json, os, subprocess, sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import golden  # noqa: E402
import release  # noqa: E402
from test_golden import CASE, Fake  # noqa: E402

GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
GREEN = {"ok": True, "exit": 0, "passed": 1, "failed": 0, "skipped": 0, "errors": 0, "out": ""}


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def checkouts(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    git(main, "config", "user.email", "t@t")
    git(main, "config", "user.name", "t")
    (main / "README.md").write_text("x\n")
    git(main, "add", ".")
    git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", "-b", "b1", str(wt))
    return main.resolve(), wt.resolve()


def test_results_file_main_checkout(checkouts):
    main, _ = checkouts
    assert golden.results_file(main) == main / ".superlite" / "golden-results.jsonl"


def test_results_file_linked_worktree_goes_to_main(checkouts):
    main, wt = checkouts
    assert golden.results_file(wt) == main / ".superlite" / "golden-results.jsonl"
    assert golden.results_file(str(wt)) == main / ".superlite" / "golden-results.jsonl"


def test_results_file_outside_git_stays_at_root(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert golden.results_file(d) == d.resolve() / ".superlite" / "golden-results.jsonl"


def test_run_from_worktree_keeps_root_for_cases_and_plugin(checkouts, monkeypatch):
    main, wt = checkouts
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    roots, seen = [], []
    monkeypatch.setattr(golden.golden_case, "cases", lambda root: roots.append(Path(root)) or [{**CASE, "id": "large"}])

    def fake_run(cases, src, out, rerun=True, timeout_s=5400, seal=None):
        seen.append((Path(src), Path(out)))
        return [{"case": "large", "passed": True, "why": []}]
    monkeypatch.setattr(golden, "run", fake_run)
    assert golden.main(["run", "--ids", "large", "--root", str(wt)]) == 0
    assert roots == [wt]
    assert seen == [(wt, main / ".superlite" / "golden-results.jsonl")]


def test_run_from_worktree_saves_rows_and_patch_in_main(checkouts, monkeypatch, capsys):
    main, wt = checkouts
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(golden.golden_case, "cases", lambda root: [{**CASE, "base": "abc"}])
    fake = Fake()
    fake.patch = lambda tree, base: "diff --git a/a b/a\n"
    monkeypatch.setattr(golden, "golden_seal", fake)
    monkeypatch.setattr(golden, "hidden_run", lambda case, tree: GREEN)
    monkeypatch.setattr(golden, "_run", lambda cmd, cwd=None, timeout=None: (0, "076a39a") if cmd[:2] == ["git", "rev-parse"] else (0, ""))
    assert golden.main(["run", "--ids", "small", "--no-rerun", "--root", str(wt)]) == 0
    rows = [json.loads(x) for x in (main / ".superlite" / "golden-results.jsonl").read_text().splitlines()]
    assert [(r["case"], r["passed"], r["patch"]) for r in rows] == [("small", True, "small-1.patch")]
    assert (main / ".superlite" / "golden" / "small-1.patch").read_text() == "diff --git a/a b/a\n"
    assert not (wt / ".superlite").exists()
    capsys.readouterr()
    assert golden.main(["history", "--root", str(wt)]) == 0
    assert capsys.readouterr().out.strip() == "small: runs 1 median lead $3.00 hidden 1.00 (noise from 5 runs)"


def test_history_from_worktree_reads_main(checkouts, capsys):
    main, wt = checkouts
    out = main / ".superlite" / "golden-results.jsonl"
    out.parent.mkdir()
    out.write_text("".join(json.dumps({"row": "golden", "case": "large", "lead_usd": v}) + "\n" for v in (2.0, 4.0)))
    (wt / ".superlite").mkdir()
    (wt / ".superlite" / "golden-results.jsonl").write_text(json.dumps({"row": "golden", "case": "large", "lead_usd": 9.0}) + "\n")
    assert golden.main(["history", "--root", str(wt)]) == 0
    assert capsys.readouterr().out.strip() == "large: runs 2 median lead $3.00 (noise from 5 runs)"


def test_release_golden_writes_main_results(checkouts, monkeypatch):
    main, wt = checkouts
    monkeypatch.setattr(release.golden_case, "cases", lambda root: [{"id": i} for i in ("small", "typical", "large")])
    seen = []

    def fake_gold(cases, src, out, rerun=True, timeout_s=5400, seal=None):
        seen.append((Path(src), Path(out)))
        return [{"case": c["id"], "passed": True, "why": []} for c in cases]
    monkeypatch.setattr(release.golden, "run", fake_gold)
    assert release._golden(wt, "minor") == 0
    assert seen == [(wt, main / ".superlite" / "golden-results.jsonl")]
