"""Feedback triage (#371): every counted entry shows under a group or on the held-back line, auto rule-blocks
group by rule and blocked target pattern, and a rule-block joins the hand-written group that names its target."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
SCRIPT = SCRIPTS / "feedback.py"
sys.path.insert(0, str(SCRIPTS))
import feedback  # noqa: E402

HELD = "## held back: 2 one-off auto entries (an auto group is listed from 2 entries on)"


def triage(tmp_path):
    f = tmp_path / "issues.json"
    f.write_text("[]", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "triage", "--issues", str(f)], capture_output=True, text=True,
                       cwd=tmp_path, env=dict(os.environ))
    assert r.returncode == 0, r.stderr
    return r.stdout


def put(eid, text, kind="bug", date="2026-11-01T10:00:00Z", **extra):
    f = Path(os.environ["SUPERLITE_HOME"]) / "feedback.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    row = {"v": 1, "id": eid, "date": date, "host": "h", "kind": kind, "text": text, "version": "1.5.85",
           "harness": "claude-code", "project": "p", "session": "", "plan": "", **extra}
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def block(eid, target, date="2026-11-01T11:00:00Z", tool="Bash"):
    put(eid, f"{tool} rule-block: {target}", kind="auto", date=date, tool=tool, reason="rule-block", target=target)


def auto(target, reason="rule-block", tool="Bash"):
    return {"kind": "auto", "tool": tool, "reason": reason, "target": target}


def ids_lines(out):
    return [line[len("- ids: "):].split() for line in out.splitlines() if line.startswith("- ids: ")]


def test_split_target_strips_the_rule_and_cwd_suffix():
    assert feedback.split_target("tests/scripts/? (rule code, cwd ~/github/p)") == ("tests/scripts/?", "code")
    assert feedback.split_target(".superlite/prime.md (rule protected)") == (".superlite/prime.md", "protected")
    assert feedback.split_target("src/a.py (cwd ~/x)") == ("src/a.py", "")
    assert feedback.split_target("superlite:researcher (fleet on) (rule fleet, cwd ~/w)") == ("superlite:researcher", "fleet")
    assert feedback.split_target("python3 -c 'print(1)'") == ("python3 -c 'print(1)'", "")
    assert feedback.split_target("src/a.py") == ("src/a.py", "")
    assert feedback.split_target("") == ("", "")


def test_blocked_path_and_pattern():
    assert feedback.blocked_path("tests/scripts/?") == "tests/scripts/?"
    assert feedback.blocked_path("cat >> .superlite/progress.md <<'EOF' Ruling: x") == ".superlite/progress.md"
    assert feedback.blocked_path("python3 - <<'EOF'") == ""
    assert feedback.blocked_path("rm '~/p/src/a.py';") == "~/p/src/a.py"
    assert feedback.blocked_path("superlite:researcher") == ""
    assert feedback.target_pattern(".superlite/last-wait.txt") == ".superlite/*"
    assert feedback.target_pattern("cat >> .superlite/progress.md <<'EOF'") == ".superlite/*"
    assert feedback.target_pattern("tests/scripts/?") == "tests/scripts/*"
    assert feedback.target_pattern("python3 - <<'EOF'") == "python3"
    assert feedback.target_pattern("superlite:researcher") == "superlite:researcher"
    assert feedback.target_pattern("") == ""


def test_rule_block_signature_has_rule_and_pattern():
    a = feedback.auto_sig(auto(".superlite/last-wait.txt (rule protected, cwd ~/p)"))
    b = feedback.auto_sig(auto(".superlite/prime.md (rule protected, cwd ~/q)"))
    c = feedback.auto_sig(auto("tests/scripts/? (rule code, cwd ~/p)"))
    d = feedback.auto_sig(auto("python3 - <<'EOF' (rule code, cwd ~/p)"))
    e = feedback.auto_sig(auto(".superlite/prime.md (rule code)"))
    assert a == b == ("Bash", "rule-block", "protected", ".superlite/*")
    assert len({a, c, d, e}) == 4
    assert feedback.auto_sig(auto("src/a.py", reason="exception", tool="commit_task")) == ("commit_task", "exception")
    assert feedback.auto_sig(auto("src/b.py", reason="exception", tool="commit_task")) == ("commit_task", "exception")


def test_unrelated_rule_blocks_get_their_own_groups(tmp_path):
    block("a00000000001", "python3 - <<'EOF' (rule code, cwd ~/p)")
    block("a00000000002", "python3 -c 'print(1)' (rule code, cwd ~/q)", date="2026-11-02T11:00:00Z")
    block("a00000000003", ".superlite/last-wait.txt (rule protected, cwd ~/p)")
    block("a00000000004", ".superlite/progress.md (rule protected, cwd ~/q)", date="2026-11-02T11:00:00Z")
    block("a00000000005", "tests/scripts/? (rule code, cwd ~/p)")
    block("a00000000006", "tests/scripts/? (rule code, cwd ~/q)", date="2026-11-02T11:00:00Z")
    out = triage(tmp_path)
    assert "6 untriaged entries, 3 groups" in out and "held back" not in out
    assert sorted(sorted(i) for i in ids_lines(out)) == [["a00000000001", "a00000000002"],
                                                         ["a00000000003", "a00000000004"],
                                                         ["a00000000005", "a00000000006"]]


def test_rule_block_joins_the_handwritten_entry_naming_its_target(tmp_path):
    put("b00000000001", "guard blocks zsh array files=(tests/scripts/test_*.py ...) as a write to tests/scripts/?",
        date="2026-11-03T10:00:00Z")
    block("b00000000002", "tests/scripts/? (rule code, cwd ~/p)", date="2026-11-01T11:00:00Z")
    block("b00000000003", ".superlite/prime.md (rule protected, cwd ~/p)")
    out = triage(tmp_path)
    assert "3 untriaged entries, 1 groups, 1 held back" in out
    assert ids_lines(out)[0] == ["b00000000001", "b00000000002"]
    assert "## 1. ×2 auto, bug: guard blocks zsh array" in out
    assert "- seen: 2026-11-01..2026-11-03" in out


def test_a_path_inside_a_longer_path_does_not_join(tmp_path):
    put("e00000000001", "lint is slow on xsrc/a.py.bak files", date="2026-11-03T10:00:00Z")
    block("e00000000002", "src/a.py (rule code, cwd ~/p)")
    out = triage(tmp_path)
    assert "2 untriaged entries, 1 groups, 1 held back" in out
    assert ids_lines(out) == [["e00000000001"], ["e00000000002"]]


def test_held_back_line_names_every_hidden_entry(tmp_path):
    put("c00000000001", "probe run hangs on windows")
    block("c00000000002", "src/a.py (rule code, cwd ~/p)")
    put("c00000000003", "run_tests no-result", kind="auto", tool="run_tests", reason="no-result", target="")
    out = triage(tmp_path)
    lines = out.splitlines()
    assert "3 untriaged entries, 1 groups, 2 held back" in out
    assert lines[lines.index(HELD) + 1] == "- ids: c00000000002 c00000000003"
    assert {i for ids in ids_lines(out) for i in ids} == {"c00000000001", "c00000000002", "c00000000003"}
    assert "run_tests" not in out


def test_no_held_back_text_when_nothing_is_held(tmp_path):
    put("d00000000001", "probe run hangs on windows")
    out = triage(tmp_path)
    assert "1 untriaged entries, 1 groups" in out and "held back" not in out


def test_command_parens_without_a_space_are_not_the_suffix():
    assert feedback.split_target("echo $(cwd x)") == ("echo $(cwd x)", "")
    assert feedback.split_target("echo $(rule x)") == ("echo $(rule x)", "")


def test_a_longer_filename_with_the_same_stem_does_not_name_the_path():
    assert not feedback.names_path("see a/b.py.bak", "a/b.py")
    assert feedback.names_path("see a/b.py.", "a/b.py")
    assert feedback.names_path("see a/b.py, then", "a/b.py")
