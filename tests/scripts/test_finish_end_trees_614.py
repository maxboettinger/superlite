"""#614: finish and `orchestrator end` drop the run's idle test trees and orphaned DerivedData, one stderr line."""
from __future__ import annotations

import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import orchestrator  # noqa: E402
import state  # noqa: E402
import trees  # noqa: E402

LINE0 = "removed 1 test tree(s) and 0 orphaned DerivedData folder(s), 0.0 GB"


def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    for cmd in (["init", "-q"], ["config", "user.email", "a@b.c"], ["config", "user.name", "n"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True)
    (r / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "-C", str(r), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "init"], check=True)
    sd = r / ".superlite"
    sd.mkdir()
    (sd / "progress.md").write_text("- commit T1 abcdef1234 t1\n", encoding="utf-8")
    (sd / "incidents.jsonl").write_text("", encoding="utf-8")
    (sd / "stable.json").write_text("{}", encoding="utf-8")
    plan = sd / "plan.md"
    plan.write_text("# plan\n", encoding="utf-8")
    return r, plan


def fake(monkeypatch, names, calls=None):
    def clean_idle(root):
        if calls is not None:
            calls.append(root)
        return list(names)
    monkeypatch.setattr(trees, "clean_idle", clean_idle, raising=False)
    monkeypatch.setattr(trees, "sweep_derived_data", lambda home=None: (0, 0))


def test_finish_drops_idle_trees(tmp_path, monkeypatch, capsys):
    r, plan = repo(tmp_path)
    calls = []
    fake(monkeypatch, ["T1"], calls)
    finish.main(["--plan", str(plan)])
    assert [str(c) for c in calls] == [str(r)]
    assert f"finish: {LINE0}" in capsys.readouterr().err


def test_end_drops_idle_trees(tmp_path, monkeypatch, capsys):
    r, plan = repo(tmp_path)
    fake(monkeypatch, ["T1"])
    assert orchestrator.main(["end", "--plan", str(plan)]) == 0
    assert f"orchestrator: {LINE0}" in capsys.readouterr().err


def test_no_line_when_nothing_removed(tmp_path, monkeypatch, capsys):
    r, plan = repo(tmp_path)
    fake(monkeypatch, [])
    assert finish.main(["--plan", str(plan)]) == 0
    assert "removed" not in capsys.readouterr().err


def test_finish_stdout_unchanged(tmp_path, monkeypatch, capsys):
    r, plan = repo(tmp_path)
    fake(monkeypatch, [])
    finish.main(["--plan", str(plan)])
    plain = capsys.readouterr()
    fake(monkeypatch, ["T1"])
    finish.main(["--plan", str(plan)])
    with_trees = capsys.readouterr()
    assert with_trees.out == plain.out
    assert "finish: removed 1 test tree(s)" in with_trees.err


def test_cleanup_error_is_ignored(tmp_path, monkeypatch, capsys):
    r, plan = repo(tmp_path)

    def boom(root):
        raise OSError("x")
    monkeypatch.setattr(trees, "clean_idle", boom, raising=False)
    assert finish.main(["--plan", str(plan)]) == 0
    assert orchestrator.main(["end", "--plan", str(plan)]) == 0


def test_end_refused_cleans_nothing(tmp_path, monkeypatch):
    r, plan = repo(tmp_path)
    calls = []
    fake(monkeypatch, ["T1"], calls)
    monkeypatch.setattr(state, "live_owner", lambda sd: "other-session")
    assert orchestrator.main(["end", "--plan", str(plan)]) == 2
    assert calls == []


def test_end_cleans_run_root(tmp_path, monkeypatch):
    r, plan = repo(tmp_path)
    calls = []
    fake(monkeypatch, [], calls)
    assert orchestrator.main(["end", "--plan", str(plan)]) == 0
    assert [str(c) for c in calls] == [str(r)]


def test_busy_tree_survives_finish(tmp_path, monkeypatch, capsys):
    """clean_idle (T1) keeps a busy tree: finish reports only what it returned (T1 e.g.: T3 busy -> T1, worker-W2)."""
    r, plan = repo(tmp_path)
    fake(monkeypatch, ["T1", "worker-W2"])
    finish.main(["--plan", str(plan)])
    assert "removed 2 test tree(s)" in capsys.readouterr().err
