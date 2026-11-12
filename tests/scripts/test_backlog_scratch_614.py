"""#614: the backlog worktree cleanup sweeps Xcode build folders from the worktree's session scratchpads."""
import json
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import trees  # noqa: E402


@pytest.fixture
def sweep(monkeypatch, tmp_path):
    """Swappable: a fake sweep by default, the real trees.sweep_scratch_builds with SUPERLITE_REAL=1."""
    import os
    if os.environ.get("SUPERLITE_REAL") == "1":
        monkeypatch.setenv("SUPERLITE_SCRATCH_HOME", str(tmp_path / "scratch"))
        return None
    calls = []

    def fake(wt, home=None):
        calls.append(str(wt))
        return (1, 0)
    monkeypatch.setattr(trees, "sweep_scratch_builds", fake, raising=False)
    return calls


def test_cleanup_sweeps_scratch_builds(sweep, tmp_path, capsys):
    wt = tmp_path / "wt"; wt.mkdir()
    home = tmp_path / "scratch"
    slug = str(wt).replace("/", "-")
    dd = home / slug / "s" / "scratchpad" / "dd"
    (dd / "Build").mkdir(parents=True); (dd / "Logs").mkdir()
    assert backlog_run.project_cleanup(tmp_path, wt, "b", "B1") is None
    assert capsys.readouterr().out == "B1 scratch builds: removed 1 folder(s), 0.0 GB\n"
    if sweep is None:
        assert not dd.exists()
    else:
        assert sweep == [str(wt)]


def test_sweep_runs_without_cleanup_cmd(sweep, tmp_path):
    wt = tmp_path / "wt"; wt.mkdir()
    assert not (tmp_path / ".superlite" / "cleanup-cmd.json").exists()
    assert backlog_run.project_cleanup(tmp_path, wt, "b", "B1") is None
    if sweep is not None:
        assert sweep == [str(wt)]


def test_sweep_error_never_fails_cleanup(tmp_path, monkeypatch, capsys):
    def boom(wt, home=None):
        raise OSError("disk")
    monkeypatch.setattr(trees, "sweep_scratch_builds", boom, raising=False)
    wt = tmp_path / "wt"; wt.mkdir()
    sd = tmp_path / ".superlite"; sd.mkdir()
    (sd / "cleanup-cmd.json").write_text(json.dumps({"cleanup": "touch ran"}))
    assert backlog_run.project_cleanup(tmp_path, wt, "b", "B1") is None
    assert capsys.readouterr().out == ""
    assert (wt / "ran").exists()
