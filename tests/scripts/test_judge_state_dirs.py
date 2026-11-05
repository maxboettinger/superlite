# tests/scripts/test_judge_state_dirs.py
import io, json, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402

@pytest.fixture
def d(tmp_path):
    proj, sd, parent = tmp_path / "proj", tmp_path / "home" / "sessions" / "s1", tmp_path / "main" / ".superlite"
    for p in (proj / ".superlite", sd, parent):
        p.mkdir(parents=True)
    return proj, sd, parent

@pytest.mark.parametrize("mode", ["idle", "active", "human"])
def test_state_folder_files_are_protected_by_absolute_path(d, mode):
    proj, sd, _ = d
    for name in ("orchestrator.json", "human-replies.jsonl", "backlog.json"):
        assert gj.judge(f"printf x > {sd / name}", str(proj), str(proj), mode, sds=(str(sd),)).kind == "protected", name
        assert gj.judge(f"printf x > {sd / name}", str(proj), str(proj), mode) is None, name
    assert gj.judge(f"printf x > {sd / 'progress.md'}", str(proj), str(proj), mode, sds=(str(sd),)) is None

def test_symlinked_folder_and_backlog_name(d, tmp_path):
    proj, sd, _ = d
    (tmp_path / "alias").symlink_to(sd)
    assert gj.judge(f"printf x > {tmp_path / 'alias' / 'orchestrator.json'}", str(proj), str(proj), "idle", sds=(str(sd),)).kind == "protected"
    assert gj.judge("printf x > .superlite/backlog.json", str(proj), str(proj), "idle").kind == "protected"
    assert gj.judge("printf x > .superlite/backlog/B1.md", str(proj), str(proj), "active") is None

def test_cli_takes_the_parent_folder_from_the_environment(d, monkeypatch, capsys):
    proj, sd, parent = d
    def run(target):
        cmd = {"tool_name": "Bash", "tool_input": {"command": f"printf x > {target}"}, "cwd": str(proj)}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(cmd)))
        return gj.main(["--mode", "idle", "--project", str(proj), "--sd", str(sd)]), capsys.readouterr().err
    monkeypatch.delenv("SUPERLITE_FLEET_PARENT_DIR", raising=False)
    assert run(sd / "orchestrator.json")[0] == 2 and run(parent / "backlog.json")[0] == 0
    monkeypatch.setenv("SUPERLITE_FLEET_PARENT_DIR", str(parent))
    rc, err = run(parent / "backlog.json")
    assert rc == 2 and "sl backlog" in err and run(parent / "backlog" / "B1.md")[0] == 0
