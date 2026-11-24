"""#1070: a log redirected into a git-ignored .build/ through a known variable passes; #1069: the hint line names the no-capture form."""
import io, json, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402
import guard_tools as gt  # noqa: E402


def git(P, *a):
    subprocess.run(["git", "-C", str(P), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


@pytest.fixture
def P(tmp_path):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / "docs" / "plans").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text("# Plan\n\n### T1 a\n**Owns:** src/a.swift\n\n### T2 b\n**Owns:** src/b.swift\n")
    (p / "src" / "a.swift").write_text("x\n")
    (p / ".gitignore").write_text(".build/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    git(p, "add", "-A")
    git(p, "commit", "-q", "-m", "init")
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def j(P, cmd):
    return gj.judge(cmd, cwd=str(P), project=str(P), mode="active", sds=(str(P / ".superlite"),))


def test_known_variable_log_target_passes(P):
    assert j(P, 'LOG=.build/ios-test.log; maxapp test > "$LOG" 2>&1; tail -5 "$LOG"') is None


def test_variable_in_file_name_passes(P):
    assert j(P, "B=b66; maxapp smoke > .build/smoke-$B.log 2>&1") is None


def test_loop_variable_targets_pass(P):
    assert j(P, "for n in 1 2; do maxapp test > .build/smoke-$n.log 2>&1; done") is None


def test_variable_target_not_ignored_blocks(P):
    v = j(P, 'LOG=src/x.log; maxapp test > "$LOG"')
    assert v is not None and v.kind == "code" and v.why == "not git-ignored"


def test_two_values_one_not_ignored_blocks(P):
    v = j(P, 'L=.build/a.log; true && L=src/a.swift; echo x > "$L"')
    assert v is not None and v.kind == "code"


def test_variable_symlink_target_blocks(P):
    (P / ".build").mkdir()
    (P / ".build" / "lnk").symlink_to(P / "src")
    v = j(P, 'D=.build/lnk; echo x > "$D/a.swift"')
    assert v is not None and v.kind == "code"


def test_literal_target_unchanged(P):
    assert j(P, "maxapp test > .build/ios-test.log 2>&1") is None
    assert j(P, "maxapp test > src/x.log").kind == "code"


def _main(P, cmd, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(P)})))
    rc = gj.main(["--mode", "active", "--project", str(P), "--sd", str(P / ".superlite")])
    return rc, capsys.readouterr().err.strip().splitlines()


def test_unknown_build_name_blocks_and_names_scratch(P, monkeypatch, capsys):
    rc, err = _main(P, "maxapp test > .build/run-$(date +%s).log", monkeypatch, capsys)
    assert rc == 2
    assert any(x.startswith("- Logs and command output: redirect them into .superlite/scratch/") for x in err)


def test_captured_wait_line_hint_line(P, monkeypatch, capsys):
    cmd = "SL=/u/skills/subagent-driven-development/scripts/sl; w=$(\"$SL\" run_tests --full --background 2>&1 | sed -n 's/^wait: //p'); eval \"$w\""
    rc, err = _main(P, cmd, monkeypatch, capsys)
    assert rc == 2
    assert err[-3] == gt.RUN_TESTS_CAPTURE_HINT
    assert err[-2] == "Unresolved word: eval $w: text the guard cannot resolve"
    assert err[-1].startswith("Blocked command: ")


def test_non_sl_capture_keeps_old_hint(P, monkeypatch, capsys):
    rc, err = _main(P, "B=$(awk '{print $1}' f); echo x >> \"$B\"", monkeypatch, capsys)
    assert rc == 2 and err[-3] == gj.UNRESOLVED_HINT and err[-2] == "Unresolved word: $B"
