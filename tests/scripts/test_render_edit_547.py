"""#547: `sl render_edit` records a lead's throwaway render-check edits so the guard allows them until `restore`."""
from __future__ import annotations

import json
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import render_edit  # noqa: E402

PLAN = "# Plan\n\n### T3 seed\n**Owns:** Demo/Owned.swift\n**Tests:** fast\n"


def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    (r / "Demo").mkdir(parents=True)
    for cmd in (["init", "-q"], ["config", "user.email", "a@b.c"], ["config", "user.name", "n"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True)
    (r / "Demo" / "Seed.swift").write_text("let a = 1\n", encoding="utf-8")
    (r / "Demo" / "Owned.swift").write_text("let o = 1\n", encoding="utf-8")
    (r / "plan.md").write_text(PLAN, encoding="utf-8")
    subprocess.run(["git", "-C", str(r), "add", "."], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "init"], check=True)
    (r / ".superlite").mkdir()
    monkeypatch.chdir(r)
    return r


def test_start_records_and_restore_reverts(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    assert render_edit.main(["start", "Demo/Seed.swift"]) == 0
    f = r / ".superlite" / "render-edits.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["files"] == {"Demo/Seed.swift": {"existed": True}}
    assert isinstance(data["started"], (int, float))
    assert f.read_text(encoding="utf-8") == json.dumps(data, indent=1, sort_keys=True)
    assert render_edit.applied(r / ".superlite") == ["Demo/Seed.swift"]
    (r / "Demo" / "Seed.swift").write_text("let a = 99\n", encoding="utf-8")
    capsys.readouterr()
    assert render_edit.main(["restore"]) == 0
    assert "restored Demo/Seed.swift" in capsys.readouterr().out
    assert (r / "Demo" / "Seed.swift").read_text(encoding="utf-8") == "let a = 1\n"
    assert render_edit.applied(r / ".superlite") == []


def test_new_file_is_deleted_on_restore(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    assert render_edit.main(["start", "Demo/New.swift"]) == 0
    assert json.loads((r / ".superlite" / "render-edits.json").read_text(encoding="utf-8"))["files"] == {
        "Demo/New.swift": {"existed": False}}
    (r / "Demo" / "New.swift").write_text("x\n", encoding="utf-8")
    assert render_edit.main(["restore", "Demo/New.swift"]) == 0
    assert not (r / "Demo" / "New.swift").exists()
    assert render_edit.applied(r / ".superlite") == []


def test_refuses_dirty_file(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    (r / "Demo" / "Seed.swift").write_text("dirty\n", encoding="utf-8")
    assert render_edit.main(["start", "Demo/Seed.swift"]) == 2
    assert "has uncommitted changes" in capsys.readouterr().err
    assert render_edit.applied(r / ".superlite") == []


def test_refuses_task_owned_file(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    assert render_edit.main(["start", "Demo/Owned.swift", "--plan", str(r / "plan.md")]) == 2
    assert "owned by T3" in capsys.readouterr().err
    (r / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(r / "plan.md")}), encoding="utf-8")
    assert render_edit.main(["start", "Demo/Owned.swift"]) == 2
    assert "owned by T3" in capsys.readouterr().err


def test_refuses_outside_root_and_protected(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    assert render_edit.main(["start", "../x"]) == 2
    assert "outside" in capsys.readouterr().err
    assert render_edit.main(["start", ".superlite/orchestrator.json"]) == 2
    assert "protected" in capsys.readouterr().err
    assert render_edit.applied(r / ".superlite") == []


def test_status_exit_1_when_applied(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    assert render_edit.main(["status"]) == 0
    render_edit.main(["start", "Demo/Seed.swift"])
    capsys.readouterr()
    assert render_edit.main(["status"]) == 1
    assert "Demo/Seed.swift" in capsys.readouterr().out


def test_no_args_prints_usage(tmp_path, monkeypatch, capsys):
    repo(tmp_path, monkeypatch)
    assert render_edit.main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_failed_restore_keeps_progress_and_restart_resets_started(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    f = r / ".superlite" / "render-edits.json"
    f.write_text(json.dumps({"files": {"Demo/Seed.swift": {"existed": True}, "Demo/Zzz.swift": {"existed": True}},
                             "started": 1}), encoding="utf-8")
    (r / "Demo" / "Seed.swift").write_text("x\n", encoding="utf-8")
    assert render_edit.main(["restore"]) == 2
    assert render_edit.applied(r / ".superlite") == ["Demo/Zzz.swift"]
    f.write_text(json.dumps({"files": {}, "started": 1}), encoding="utf-8")
    assert render_edit.main(["start", "Demo/Seed.swift"]) == 0
    assert json.loads(f.read_text(encoding="utf-8"))["started"] > 1


def test_folder_and_glob_owns_refuse_inner_file_f_t7_1(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    (r / "plan2.md").write_text("# Plan\n\n### T3 seed\n**Owns:** Demo/\n**Tests:** fast\n", encoding="utf-8")
    assert render_edit.main(["start", "Demo/Seed.swift", "--plan", str(r / "plan2.md")]) == 2
    assert "owned by T3" in capsys.readouterr().err
    (r / "plan3.md").write_text("# Plan\n\n### T4 seed\n**Owns:** Demo/*.swift\n**Tests:** fast\n", encoding="utf-8")
    assert render_edit.main(["start", "Demo/Seed.swift", "--plan", str(r / "plan3.md")]) == 2
    assert "owned by T4" in capsys.readouterr().err


def test_record_goes_to_bound_run_folder_f_t7_2(tmp_path, monkeypatch, capsys):
    r = repo(tmp_path, monkeypatch)
    run = tmp_path / "bound"
    run.mkdir()
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(run))
    assert render_edit.main(["start", "Demo/Seed.swift"]) == 0
    assert (run / "render-edits.json").exists()
    assert not (r / ".superlite" / "render-edits.json").exists()
    assert render_edit.main(["restore"]) == 0
    assert render_edit.applied(run) == []


def test_refuses_symlink_and_hard_link(tmp_path, monkeypatch, capsys):
    import os
    r = repo(tmp_path, monkeypatch)
    os.symlink(r / "Demo" / "Seed.swift", r / "Demo" / "Sym.swift")
    assert render_edit.main(["start", "Demo/Sym.swift"]) == 2
    assert "is a link" in capsys.readouterr().err
    os.link(r / "Demo" / "Seed.swift", r / "Demo" / "Hard.swift")
    assert render_edit.main(["start", "Demo/Seed.swift"]) == 2
    assert "is a link" in capsys.readouterr().err
