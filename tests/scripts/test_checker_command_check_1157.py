"""#1157: a lead's project check that writes files goes to a checker; the guard's block text names that route."""
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import guard_judge as gj  # noqa: E402

HOOK = ROOT / "hooks" / "block-coordinator-edits"
BASH = shutil.which("bash")
BULLET = ("- A project check that writes files (a reproduction or verification command such as `make record-fixtures`): "
          "give it to a checker as a `C<n>: run <command>; see: <what must hold>` line (fleet on: "
          "`sl fleet spawn --role checker --brief <file>`; fleet off: Agent `superlite:checker`); it runs the command "
          "in the run root, reports, and puts back what it wrote (agents/checker.md, Command checks).")
RENDER = "- A throwaway edit to check a render"
TWO = "# Plan\n\n### T1 a\n**Owns:** src/a.py\n\n### T2 b\n**Owns:** src/b.py\n"


def test_messages_hold_the_bullet_once_after_render_line():
    code = gj.MESSAGES["code"]
    assert code.count(BULLET) == 1
    i = code.index(BULLET)
    assert code[i - 1].startswith(RENDER)
    assert code[-1].startswith("- After the run,")


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / "docs" / "plans").mkdir(parents=True)
    (p / ".superlite").mkdir()
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(TWO)
    (p / "Makefile").write_text("record-fixtures:\n\tpython3 rec.py > src/recorded-v2.json\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def test_judge_block_names_checker_route(proj, monkeypatch, capsys):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "python3 Scripts/record_fixtures.py > src/recorded-v2.json"}, "cwd": str(proj)})
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    rc = gj.main(["--mode", "active", "--project", str(proj), "--sd", str(proj / ".superlite")])
    err = capsys.readouterr().err.splitlines()
    assert rc == 2
    assert BULLET in err
    assert err[err.index(BULLET) - 1].startswith(RENDER)


def _hook(p, tool, path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("SUPERLITE_STATE_DIR", "SUPERLITE_SESSION_ID") and not k.startswith("SUPERLITE_FLEET_")}
    env["CLAUDE_PROJECT_DIR"] = str(p)
    raw = json.dumps({"tool_name": tool, "tool_input": {"file_path": path}, "cwd": str(p)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_hook_edit_block_names_checker_route(proj, tool):
    r = _hook(proj, tool, str(proj / "src" / "a.py"))
    lines = r.stderr.splitlines()
    assert r.returncode == 2
    assert lines.count(BULLET) == 1
    assert lines[lines.index(BULLET) - 1].startswith(RENDER)
    assert lines[-1] == "Blocked target: src/a.py"


def test_checker_md_command_checks():
    text = (ROOT / "agents" / "checker.md").read_text(encoding="utf-8")
    sec = text.split("## Command checks", 1)[1].split("\n## ", 1)[0]
    for part in ("`C<n>: run <command>; see: <what must hold>`", "`make record-fixtures`",
                 "`git -C <ROOT> status --porcelain`", "NOT REACHABLE", "`git -C <ROOT> checkout HEAD -- <path>`",
                 "`??`", "`.superlite/check/C<n>-"):
        assert part in sec, part
    assert "Change no product or test file, commit nothing, and leave git alone (no stash, checkout, reset or branch)." in text
    assert "a command check puts back what its own command wrote (Command checks)" in text
    assert "A command check is judged from its command's output instead (Command checks)." in text


def test_fleet_md_and_hooks_md_name_the_route():
    fleet = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    checker = next(x for x in fleet.splitlines() if x.startswith("- Checker command check (#1157): "))
    for part in ("`make record-fixtures`", "`C<n>: run <command>; see: <what must hold>`", "Command checks", "#1157"):
        assert part in checker, part
    hooks = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    bullet = [x for x in hooks.splitlines() if x.startswith("- `block-coordinator-edits`, project checks that write files (#1157):")]
    assert len(bullet) == 1
    assert "agents/checker.md" in bullet[0] and "Edit and Write" in bullet[0]


def test_fleet_md_checker_bullet_does_not_claim_guard_sees_make():
    fleet = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    checker = next(x for x in fleet.splitlines() if x.startswith("- Checker command check (#1157): "))
    assert "guard blocks" not in checker
    assert checker.startswith("- Checker command check (#1157): a project command that writes tracked files")
    assert "which the coordinator must not run itself" in checker
