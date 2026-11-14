"""#781: `source <(...)` of a print-only read of git-tracked files passes; unresolved blocks name the way out for
their cause; the scratch note names the subprocess programs the guard reads (#780)."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import guard_judge  # noqa: E402
from guard_judge import judge  # noqa: E402

SL = str(ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl")
GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
NOTE = ("A subprocess call whose program is not a string literal (`[prog, ...]`) is judged unknown; a list name bound "
        "once to a literal list (used only as the call's argument or a `*` splat) counts as that list, `sys.executable` "
        "as python3, and a later argument that is not a literal is judged like an unknown shell variable.")


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "p"
    (p / ".superlite" / "scratch").mkdir(parents=True)
    (p / "tools").mkdir()
    (p / "tools" / "defs.sh").write_text("A=1\nf() { echo hi; }\n# end\n")
    (p / "tools" / "b.sh").write_text("B=2\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "add", "tools"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   check=True, env=GIT_ENV)
    (p / ".superlite" / "bad.sh").write_text("rm -rf src\n")
    return str(p)


def _j(p, cmd):
    return judge(cmd, p, p, "active", (p + "/.superlite",))


def _block(p, cmd, monkeypatch, capsys):
    data = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": p}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(data)))
    rc = guard_judge.main(["--mode", "active", "--project", p, "--sd", p + "/.superlite"])
    return rc, capsys.readouterr().err.splitlines()


@pytest.mark.parametrize("cmd", [
    "source <(sed -n '1,5p' tools/defs.sh)",
    ". <(cat tools/defs.sh)",
    "source <(sed -n -e 1p -e '3,$p' tools/defs.sh)",
    "source <(head -n 2 tools/defs.sh)",
    "source <(tail -n 1 tools/defs.sh)",
    "source <(cat tools/defs.sh tools/b.sh)",
    "bash -c 'source <(sed -n \"/^A=/,/^# end/p\" tools/defs.sh); echo $A'",
    "cd tools && source <(sed -n 2p defs.sh)",
])
def test_print_only_read_of_tracked_files_passes(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("cmd", [
    "source <(sed -n '1w src/a.py' tools/defs.sh)",
    "source <(sed -n 's/A/B/p' tools/defs.sh)",
    "source <(sed '1d' tools/defs.sh)",
    "source <(sed -n \"$R\" tools/defs.sh)",
    "source <(sed -n 1p .superlite/bad.sh)",
    "source <(cat tools/defs.sh .superlite/bad.sh)",
    "source <(cat tools/missing.sh)",
    "source <(echo 'rm -rf src')",
    "source <(cat tools/defs.sh | sh)",
    "source <(cat tools/defs.sh; rm -rf src)",
    "sed() { echo 'rm -rf src'; }; source <(sed -n 1p tools/defs.sh)",
    "source <(cat \"$F\")",
    "source <(cat tools/*.sh)",
])
def test_other_process_substitutions_stay_unknown(proj, cmd):
    assert _j(proj, cmd) is not None


def test_source_block_names_the_scratch_way_out(proj, monkeypatch, capsys):
    rc, err = _block(proj, "source <(sed -n \"$R\" tools/defs.sh)", monkeypatch, capsys)
    assert rc == 2
    assert err[-3] == guard_judge.SOURCE_HINT.replace("{scratch}", ".superlite/scratch")
    assert err[-2] == 'Unresolved word: <(sed -n "$R" tools/defs.sh)'
    assert guard_judge.UNRESOLVED_HINT not in err


def test_eval_block_names_print_then_run(proj, monkeypatch, capsys):
    cmd = f"W=$({SL} run_tests --full --background 2>&1 | grep '^wait:' | sed 's/^wait: //'); eval \"$W\""
    rc, err = _block(proj, cmd, monkeypatch, capsys)
    assert rc == 2
    assert err[-3] == guard_judge.EVAL_HINT
    assert err[-2].startswith("Unresolved word: eval ")


def test_loop_built_list_names_the_also_form(proj, monkeypatch, capsys):
    files = " ".join(f"t{i}.py" for i in range(11))
    cmd = f'SL={SL}; A=""; for f in {files}; do A="$A --also tests/$f"; done; $SL commit_task T1 $A'
    rc, err = _block(proj, cmd, monkeypatch, capsys)
    assert rc == 2
    assert err[-3] == guard_judge.MANY_HINT
    assert err[-2] == "Unresolved word: too many variable values"


def test_other_unresolved_words_keep_the_generic_hint(proj, monkeypatch, capsys):
    rc, err = _block(proj, 'printf x >> "$f"', monkeypatch, capsys)
    assert rc == 2
    assert err[-3] == guard_judge.UNRESOLVED_HINT


def test_scratch_note_names_readable_programs(proj, monkeypatch, capsys):
    rc, err = _block(proj, "printf x > src/a.py", monkeypatch, capsys)
    assert rc == 2
    assert any(line.endswith(NOTE) for line in err)


@pytest.mark.parametrize("cmd", [
    "source tools/b.sh; source <(cat tools/defs.sh)",
    "eval 'true'; source <(cat tools/defs.sh)",
    ". tools/b.sh; . <(cat tools/defs.sh)",
    "bash -c 'source tools/b.sh'; source <(cat tools/defs.sh)",
])
def test_print_only_read_after_a_source_or_eval_stays_unknown(proj, cmd):  # F-T2-9
    assert _j(proj, cmd) is not None


def test_print_only_read_after_a_link_stays_unknown(proj):  # F-T2-12
    v = _j(proj, "ln -s x .superlite/scratch/y; source <(cat tools/defs.sh)")
    assert v is not None and v.rel == "?"
