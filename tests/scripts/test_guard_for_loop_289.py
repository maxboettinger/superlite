import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_judge  # noqa: E402
from guard_judge import Verdict, judge, main  # noqa: E402

UNK = Verdict("?", "?", "code")


@pytest.fixture
def P(tmp_path):
    p = (tmp_path / "p").resolve()
    for d in ("src", "docs/plans", ".superlite/linux", ".superlite/fixes"):
        (p / d).mkdir(parents=True)
    return str(p)


def run(cmd, P, mode="active", cwd=None):
    return judge(cmd, cwd or P, P, mode)


def test_issue_case_passes(P):
    cmd = f"L={P}/.superlite/linux; for v in 24 26; do echo hi > $L/node$v.log; done"
    assert run(cmd, P) is None
    assert run(cmd, P, "human") is None


def test_newline_loop_passes(P):
    assert run(f"L={P}/.superlite\nfor v in a b\ndo\n  echo hi > $L/$v.log\ndone", P) is None


@pytest.mark.parametrize("cmd", [
    "D=.superlite; for f in $D/a $D/b; do touch $f; done",
    "for v in {24,26}; do echo hi > .superlite/node$v.log; done",
    "for d in ~/x; do echo > $d/f; done",
])
def test_values_from_vars_and_braces_pass(P, cmd):
    assert run(cmd, P) is None


def test_nested_loops_pass(P):
    assert run("for a in x y; do for b in p q; do echo > .superlite/$a-$b.log; done; done", P) is None


@pytest.mark.parametrize("cmd", [
    "for v in a b; do echo $v; done | sort > .superlite/o.txt",
    "for v in a b; do echo $v; done > .superlite/o.txt",
])
def test_loop_output_redirects_pass(P, cmd):
    assert run(cmd, P) is None


@pytest.mark.parametrize("cmd", [
    "for v in .superlite/a src/x.py; do echo > $v; done",
    "for v in src/x.py .superlite/a; do echo > $v; done",
])
def test_each_value_is_judged(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"


@pytest.mark.parametrize("cmd", [
    "for f in .superlite/a src/x.py; do g=$f; echo > $g; done",
    "for f in src/x.py .superlite/a; do g=$f; echo > $g; done",
    'for f in .superlite/a src/x.py; do eval "g=$f"; echo > $g; done',
    'for f in src/x.py .superlite/a; do eval "g=$f"; echo > $g; done',
])
def test_derived_assignment_judged_per_value(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"


@pytest.mark.parametrize("cmd", [
    "for d in fixes ../src; do cd $d; echo > x; done",
    "for d in ../src fixes; do cd $d; echo > x; done",
])
def test_cd_judged_per_value(P, cmd):
    v = run(cmd, P, cwd=P + "/.superlite")
    assert v is not None and v.rel == "src/x" and v.kind == "code"


def test_body_reassigns_loop_var(P):
    v = run("for v in .superlite/a; do v=src/x; echo > $v; done", P)
    assert v is not None and v.rel == "src/x"


def test_quoted_done_is_no_keyword(P):
    v = run('for v in src/x .superlite/a; do\n"done"\necho > $v\ndone', P)
    assert v is not None and v.rel == "src/x"


def test_protected_value_blocks(P):
    v = run("for f in .superlite/a .superlite/orchestrator.json; do echo > $f; done", P, "idle")
    assert v is not None and v.kind == "protected"


def test_stale_value_not_reused(P):
    assert run("f=.superlite/a; for f in src/*.py; do echo > $f; done", P) == UNK


@pytest.mark.parametrize("lst", ["src/*.py", '"$(ls)"', "$UNSET", '"a b"', '"x*"', "{1..3}"])
def test_unreadable_list_is_unknown(P, lst):
    assert run(f"for f in {lst}; do echo > .superlite/$f; done", P) == UNK


@pytest.mark.parametrize("cmd", [
    "for f; do echo > .superlite/$f; done",
    "select f in a b; do echo > .superlite/$f; done",
    "X=a; X=b; for f in $X; do echo > .superlite/$f; done",
    "for f in a b; do echo > .superlite/$f",
    "v=src/x; for v in .superlite/a; do :; done > $v.log",
])
def test_unreadable_command_is_unknown(P, cmd):
    assert run(cmd, P) == UNK


def test_value_cap(P):
    def cmd(n):
        return "for v in " + " ".join(f"n{i}" for i in range(n)) + "; do echo > .superlite/$v; done"
    assert run(cmd(64), P) is None
    assert run(cmd(65), P) == UNK


def test_quoted_tilde_is_literal(P):
    v = run('for d in "~/x"; do echo > $d/f; done', P)
    assert v is not None and v.rel == "~/x/f" and v.kind == "code"


def test_nested_header_counts_as_block(P):
    cmd = f"cd {P}/src; for a in x; do for b in y; do :; done; continue; cd {P}/.superlite; done; echo > a.py"
    v = run(cmd, P)
    assert v is not None and v.rel == "src/a.py"


def test_unknown_verdict_names_word(P):
    v = run("echo hi > $L/node$v.log", P)
    assert v == UNK and v.word == "$L/node$v.log"
    v = run(f"L={P}/.superlite/linux; echo hi > $L/node$v.log", P)
    assert v == UNK and v.word == f"{P}/.superlite/linux/node$v.log"


@pytest.mark.parametrize("cmd,word", [
    ('rm "$X"', "$X"),
    ("xargs rm", "? (from rm)"),
    ("ls | sh", "program piped into sh"),
    ("bash <(curl -s x)", "<(curl -s x)"),
    ("source <(x)", "<(x)"),
    ("echo " + "$(echo " * 10 + "x" + ")" * 10, "nesting deeper than 8"),
])
def test_word_on_every_unknown(P, cmd, word):
    v = run(cmd, P)
    assert v is not None and v.rel == "?" and v.word == word


def test_word_on_budget(P, monkeypatch):
    monkeypatch.setattr(guard_judge, "MAX_STEPS", 0)
    v = run("echo a", P)
    assert v is not None and v.rel == "?" and v.word == "step or time budget"


def _main(P, tmp_path, monkeypatch, capsys, cmd):
    monkeypatch.delenv("SUPERLITE_FLEET_PARENT_DIR", raising=False)
    monkeypatch.delenv("SUPERLITE_GUARD_NONCE", raising=False)
    sd = tmp_path / "sd"
    sd.mkdir(exist_ok=True)
    hook = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": P}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook)))
    code = main(["--mode", "active", "--project", P, "--sd", str(sd)])
    err = capsys.readouterr().err
    rows = [json.loads(x) for x in (sd / "incidents.jsonl").read_text().splitlines()]
    return code, err, rows


def test_main_prints_and_logs_word(P, tmp_path, monkeypatch, capsys):
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, 'rm "$X"')
    assert code == 2
    assert err.splitlines()[-2:] == ["Unresolved word: $X", 'Blocked command: rm "$X"']
    assert rows[-1]["target"] == 'unresolved $X in: rm "$X"' and rows[-1]["rule"] == "code"


def test_incident_word_survives_cut(P, tmp_path, monkeypatch, capsys):
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, "echo " + "a" * 300 + "; echo hi > $Q/x")
    t = rows[-1]["target"]
    assert code == 2 and t.startswith("unresolved $Q/x in: echo aaa") and "$Q/x" in t[:200]


def test_protected_unknown_names_no_target(P, tmp_path, monkeypatch, capsys):
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, 'rm "$X"; cat .superlite/orchestrator.json')
    assert code == 2 and "never written directly" in err
    assert "Unresolved word" not in err and "Blocked command" not in err
    assert rows[-1]["target"].startswith("unresolved $X in: ")


def test_named_and_whole_tree_blocks_unchanged(P, tmp_path, monkeypatch, capsys):
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, "rm src/a")
    assert code == 2 and rows[-1]["target"] == "src/a" and "Unresolved word" not in err
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, "rm -rf .")
    assert rows[-1]["target"] == "rm -rf ." and "Unresolved word" not in err
    assert err.splitlines()[-1] == "Blocked command: rm -rf ."


@pytest.mark.parametrize("cmd", [
    "IFS=/; X=.superlite/a; for v in $X; do echo > $v; done",
    "for v in ~+/.superlite/a; do echo > $v; done",
    "for v in ~-/../.superlite/a; do echo > $v; done",
    'for v in ""; do echo > .superlite/x$v; done',
    "for v in .superlite/a; do read v; echo > $v; done",
    "for v in .superlite/a; do printf -v v src/x; echo > $v; done",
    "for v in .superlite/a; do ((v=1)); echo > $v; done",
    "for v in .superlite/a; do mapfile v < /dev/null; echo > $v; done",
])
def test_unreadable_binding_is_unknown(P, cmd):
    assert run(cmd, P) == UNK


def test_append_assignment_appends(P):
    assert run("v=.superlite; v+=/a; echo > $v", P) is None
    got = run("for v in .superlite/a; do v+=/../../src/x; echo > $v; done", P)
    assert got.rel == "src/x" and got.kind == "code"


def test_ifs_needs_the_variable_word(P):
    assert run("D=.superlite/diffs; for f in $D/a $D/b; do touch $f; done", P) is None
    assert run("IFS=/; X=.superlite/a; for v in $X; do echo > $v; done", P) == UNK


def test_append_to_unset_name_is_unknown(P):
    assert run("X+=.superlite/a; echo > $X", P) == UNK
    assert run("X=.superlite; X+=/a; echo > $X", P) is None


@pytest.mark.parametrize("cmd", [
    "for v in src/x.py .superlite/a; do break; done; echo > $v",
    "v=src/x; for v in .superlite/a; do :; done | cat; echo > $v",
    "v=src/x; for v in .superlite/a; do :; done & echo > $v",
])
def test_loop_values_stay_possible_after_done(P, cmd):
    got = run(cmd, P)
    assert got is not None and got.kind == "code" and got != UNK


def test_unknown_pre_loop_value_stays_unknown(P):
    assert run("v=$(x); for v in .superlite/a; do :; done; echo > $v", P) == UNK


@pytest.mark.parametrize("cmd", [
    'for f in src/x.py .superlite/a; do eval "g=$f"; [ -e x ] && break; done; echo > $g',
    'for f in src/x.py .superlite/a; do eval "g=$f"; done | cat; echo > $g',
])
def test_eval_copy_back_keeps_earlier_value(P, cmd):
    got = run(cmd, P)
    assert got is not None and got.kind == "code"


@pytest.mark.parametrize("cmd", [
    "s=src/x.py; for v in /../../.superlite/a; do s+=$v; done | cat; echo > $s",
    "s=src/x.py; for v in /../../.superlite/a; do s+=$v; break; done; echo > $s",
    "s=src/x.py; false && s+=/../../.superlite/a; echo > $s",
])
def test_conditional_append_keeps_old_value(P, cmd):
    got = run(cmd, P)
    assert got is not None and got.kind == "code"


def test_plain_append_stays_one_value(P):
    assert run("s=.superlite; s+=/a; echo > $s", P) is None


NESTED = "for a in docs .superlite; do for b in x.py p.md; do [ -e z ] && break 2; done; done; "


def test_variable_values_judged_in_combination(P):
    got = run(NESTED + "echo > $a/$b", P)
    assert got is not None and got.rel == "docs/x.py"
    assert run(NESTED + "echo > .superlite/$b", P) is None


def test_too_many_variable_combinations_is_unknown(P):
    loops = "".join(f"for {n} in a b c d; do for {n}{n} in e f; do :; done; done; " for n in "xyz")
    cmd = "x=1; y=1; z=1; " + loops + "echo > .superlite/$x$y$z"
    assert run(cmd, P) == UNK


@pytest.mark.parametrize("tail", ["[ -e z ] && break; done;", "done | cat;", "done &"])
def test_earlier_value_cd_and_assignment_take_effect(P, tail):
    loop = "[ -e z ] && break; done;" if tail.startswith("[") else ("done | cat;" if "cat" in tail else "done &")
    got = run(f"for d in ../src fixes; do :; {loop} cd $d; echo > x", P, cwd=P + "/.superlite")
    assert got is not None and got.rel == "src/x"
    got = run(f"for f in src/x.py .superlite/a; do :; {loop} g=$f; echo > $g", P)
    assert got is not None and got.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "v=.superlite/a; for((v=0;v<1;v++)); do echo hi > $v; done",
    "v=.superlite/a; for ((v=0;v<1;v++)); do for ((v=0;v<1;v++)); do echo hi > $v; done; done",
    "v=.superlite/a; for ((;v<1;v++)); do echo hi > $v; done",
    "v=.superlite/a; ((v++)); echo > $v",
    "v=.superlite/a; ((++v)); echo > $v",
    "v=.superlite/a; ((v--)); echo > $v",
    "v=.superlite/a; let v++; echo > $v",
    "v=.superlite/a; let 'v += 1'; echo > $v",
])
def test_arithmetic_assignment_makes_variable_unknown(P, cmd):
    assert run(cmd, P) == UNK


def test_arithmetic_for_header_with_literal_target_passes(P):
    assert run("for ((i=0;i<2;i++)); do echo hi > .superlite/n.log; done", P) is None


# --- #351: unresolved targets: .superlite/ and plan writes from an unknown directory, prose "function", the hint


@pytest.mark.parametrize("tgt", [".superlite/last-wait.txt", ".superlite/fixes/a.md"])
def test_unknown_dir_state_writes_pass(P, tgt):
    assert run(f"cd $X; echo hi > {tgt}", P) is None


@pytest.mark.parametrize("tgt,kind", [
    ("src/x.py", "code"), ("docs/a.md", "code"), ("docs/plans/x.md", "code"), ("docs/sub/plans/x.md", "code"), (".superlite/../src/x.py", "code"), ("x/.superlite/a", "code"),
    (".superlite/orchestrator.json", "protected"),
])
def test_unknown_dir_other_writes_still_block(P, tgt, kind):
    v = run(f"cd $X; echo hi > {tgt}", P)
    assert v is not None and v.rel == tgt and v.kind == kind


def test_unknown_dir_human_mode(P):
    assert run("cd $X; echo hi > .superlite/a", P, "human") is None
    v = run("cd $X; echo hi > docs/plans/x.review.md", P, "human")
    assert v is not None and v.kind == "human"
    v = run("cd $X; echo hi > docs/plans/x.md", P, "human")
    assert v is not None and v.kind == "human"


def test_variable_prefix_is_no_unknown_dir(P):
    v = run("rm $X/.superlite/a", P)
    assert v is not None and v.kind == "code" and v.word == "$X/.superlite/a"
    v = run("IFS=/; echo hi > $CLAUDE_PROJECT_DIR/.superlite/a", P)
    assert v is not None and v.kind == "code"


def test_wait_file_after_unknown_dir_passes(P, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    cmd = (f"cd {out} && SL=/x/sl && $SL fleet stop W17 2>&1 | tail -1; ( git diff main --name-only -- '*.swift' ) "
           "| sort -u | while read f; do [ -f \"$f\" ] && echo \"$f\"; done | xargs -n 20 swift format lint 2>&1 "
           "| grep -c warning; W=$($SL run_tests --full --background 2>&1 | grep '^wait:'); "
           "echo \"$W\" > .superlite/last-wait.txt; eval \"$W\" >/dev/null 2>&1")
    assert run(cmd, P) is None


def test_prose_function_word_is_no_function(P, tmp_path):
    out = tmp_path / "out"
    (out / "docs" / "plans").mkdir(parents=True)
    cmd = (f"cd {out} && P=docs/plans/x.md && python3 - $P <<'EOF'\nimport sys\np=sys.argv[1]\n"
           "open(p,'w').write('a #if DEBUG public function in Dashboard')\nEOF")
    assert run(cmd, P) is None
    assert run("cat <<'EOF' > .superlite/n.md\nf() { x; }\nEOF\necho hi > .superlite/a; cd docs", P) is None


@pytest.mark.parametrize("cmd", [
    "f() { echo hi > .superlite/a; }; cd docs; f",
    "function f { echo hi > .superlite/a; }; cd docs; f",
    "if true; then function f { echo hi > .superlite/a; }; fi; cd docs; f",
    "cat <<'EOF' > .superlite/n.md\nnotes\nEOF\nf() { echo hi > .superlite/a; }; cd docs; f",
])
def test_real_function_body_still_runs_later(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "docs/.superlite/a"


@pytest.mark.parametrize("cmd", [
    "f()\n{\necho hi > .superlite/a\n}\ncat <<'EOF' > .superlite/n.md\n{\nEOF\ncd docs; f",
    "f()\n{\necho hi > .superlite/a\n}\ncd docs; f",
])
def test_heredoc_text_does_not_hide_a_function_definition(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "docs/.superlite/a"


@pytest.mark.parametrize("cmd,word", [
    ("for B in $(awk '{print $2}' .superlite/route.txt); do echo x >> $B; done", "$B"),
    ("for B in $(cat .superlite/r.txt); do echo x > .superlite/fixes/$B.md; done", ".superlite/fixes/$B.md"),
])
def test_unresolvable_loop_targets_stay_blocked(P, cmd, word):
    v = run(cmd, P)
    assert v == UNK and v.word == word


def test_unresolved_block_names_the_supported_way(P, tmp_path, monkeypatch, capsys):
    cmd = "for B in $(awk '{print $2}' .superlite/route.txt); do echo x >> $B; done"
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, cmd)
    lines = err.splitlines()
    assert code == 2 and lines[-2:] == ["Unresolved word: $B", "Blocked command: " + cmd]
    assert lines[-3] == guard_judge.UNRESOLVED_HINT
    assert "Write or Edit tool" in guard_judge.UNRESOLVED_HINT and ".superlite/" in guard_judge.UNRESOLVED_HINT
    code, err, rows = _main(P, tmp_path, monkeypatch, capsys, "rm src/a")
    assert code == 2 and guard_judge.UNRESOLVED_HINT not in err


def test_unknown_dir_state_write_follows_links(P):
    import os
    os.makedirs(P + "/src", exist_ok=True)
    (Path(P) / "src/a.py").write_text("x")
    os.symlink("../src/a.py", P + "/.superlite/l")
    v = run("cd $X && echo hi > .superlite/l", P)
    assert v is not None and v.rel == "src/a.py"
    os.link(P + "/src/a.py", P + "/.superlite/h")
    v = run("cd $X && echo hi > .superlite/h", P)
    assert v is not None and v.kind == "code"
    v = run("cd $X && ln -s ../src/a.py .superlite/m && echo hi > .superlite/m", P)
    assert v is not None
    assert run("cd $X && echo hi > .superlite/last-wait.txt", P) is None
