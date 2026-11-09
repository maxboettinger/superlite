"""#329: chain-assigned literals, $TMPDIR resolves; `mkdir -p D;` makes D sure; scratchpad writes pass."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

from guard_judge import Verdict, judge  # noqa: E402

UNK = Verdict("?", "?", "code")


@pytest.fixture
def P(tmp_path, monkeypatch):
    p = (tmp_path / "p").resolve()
    for d in ("src", "docs/plans", ".superlite"):
        (p / d).mkdir(parents=True)
    (p / "src" / "x.py").write_text("x = 1\n")
    (p / "docs" / "plans" / "x.md").write_text("a\n")
    for name in ("P", "S", "X"):
        monkeypatch.delenv(name, raising=False)
    return str(p)


@pytest.fixture
def SP(tmp_path):
    s = (tmp_path / "scratchpad").resolve()
    s.mkdir()
    return str(s)


def run(cmd, P, mode="active"):
    return judge(cmd, P, P, mode)


def test_chain_literal_resolves(P, SP):
    assert run(f"cd {SP} && P=docs/plans/x.md; sed -i '' 's/a/b/' $P && grep -c b $P", P) is None
    assert run("true && P=docs/plans/x.md; sed -i '' 's/a/b/' $P", P) is None
    assert run(f"git status && S={SP}; cat > $S/probe.py <<'EOF'\nx\nEOF", P) is None
    assert run("if [ -e z ]; then P=.superlite/a; fi; echo hi > $P", P) is None
    assert run('true && P=.superlite/a; echo hi > "$P"', P) is None


def test_chain_literal_still_judged(P):
    v = run("false && X=src/x.py; echo hi > $X", P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"
    v = run("true && X=docs/plans/x.md; echo hi > $X", P, "human")
    assert v is not None and v.rel == "docs/plans/x.md" and v.kind == "human"


def test_env_name_stays_unknown(P, monkeypatch):
    monkeypatch.setenv("X", "/elsewhere")
    v = run("false && X=.superlite/a; echo hi > $X", P)
    assert v == UNK and v.word == "$X"


def test_tmpdir_resolves(P, tmp_path, monkeypatch):
    t = tmp_path / "T"
    t.mkdir()
    monkeypatch.setenv("TMPDIR", str(t.resolve()) + "/")
    assert run('git diff --name-only HEAD origin/main | sort > "$TMPDIR/upstream.txt"', P) is None
    assert run("echo a > ${TMPDIR}x.txt", P) is None
    assert run('cd "$TMPDIR"; cat > png.py', P) is None


def test_tmpdir_inside_project_is_code(P, monkeypatch):
    monkeypatch.setenv("TMPDIR", P + "/src")
    v = run("echo a > $TMPDIR/y.py", P)
    assert v is not None and v.rel == "src/y.py"


@pytest.mark.parametrize("value", [None, "rel/tmp"])
def test_tmpdir_unset_or_relative_stays_unknown(P, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("TMPDIR", raising=False)
    else:
        monkeypatch.setenv("TMPDIR", value)
    v = run("echo a > $TMPDIR/y.py", P)
    assert v is not None and v.word == "$TMPDIR/y.py"


def test_home_stays_unresolved(P, tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h.resolve()))
    v = run("echo hi > $HOME/x.txt", P)
    assert v is not None and v.word == "$HOME/x.txt"


@pytest.mark.parametrize("sep", ["; ", "\n"])
def test_mkdir_before_semicolon_is_sure(P, SP, sep):
    assert run(f"mkdir -p {SP}/n{sep}cd {SP}/n{sep}cat > png.py <<'EOF'\nx\nEOF", P) is None


@pytest.mark.parametrize("cmd", ["mkdir -p -m 700 {SP}/n; cd {SP}/n; cat > png.py",
                                 "mkdir -p {SP}/n & cd {SP}/n; cat > png.py"])
def test_mkdir_mode_or_background_not_sure(P, SP, cmd):
    v = run(cmd.format(SP=SP), P)
    assert v is not None and v.rel == "png.py"


@pytest.mark.parametrize("mode", ["active", "human"])
def test_scratchpad_writes_pass(P, SP, mode):
    assert run(f"cd {SP}; cat > png.py <<'EOF'\nx\nEOF", P, mode) is None
    assert run(f"S={SP}; cat > $S/probe.py <<'EOF'\nx\nEOF", P, mode) is None
    assert run(f"cd {SP} && python3 - <<'PY'\nopen('png.py','w').write('x')\nPY", P, mode) is None
    v = run(f"cd {SP}/missing; cat > png.py", P, mode)
    assert v is not None and v.rel == "png.py"


# --- #352: an array assignment NAME=(words) assigns, it runs no command


@pytest.mark.parametrize("cmd", [
    "files=(tests/scripts/test_guard*.py tests/scripts/test_x.py)\nsl run_tests --fast $files",
    "SL=/x/sl; files=(tests/scripts/test_guard*.py tests/scripts/test_x.py); $SL run_tests --fast $files",
    "files=(rm src/x.py)",
    "a=1 files+=(rm src/x.py)",
    "local -a files=(src/*.py src/x.py)",
    "declare -a files=(tee src/x.py)",
    "export A=(rm src/x.py)",
    "files=(\n  rm src/x.py\n)",
    "if true; then files=(src/*.py src/x.py); fi",
    "for f in a b; do files=(src/*.py src/$f.py); done",
])
@pytest.mark.parametrize("mode", ["active", "human"])
def test_array_assignment_runs_no_command(P, cmd, mode):
    assert run(cmd, P, mode) is None


@pytest.mark.parametrize("cmd", ["x=(a $(rm src/x.py) b)", "x=(a `touch src/x.py`)", "x=(a)>src/x.py"])
def test_array_substitution_and_redirect_still_judged(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"


@pytest.mark.parametrize("cmd", [
    "x=; (rm src/x.py)",
    "x= ;(rm src/x.py)",
    "x=\n(rm src/x.py)",
    "x=(a); x=; (rm src/x.py)",
    "x=(a; rm src/x.py)",
])
def test_subshell_after_empty_assignment_still_judged(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"


@pytest.mark.parametrize("cmd", ["x=(src/x.py); rm $x", "x=(.superlite/a); x+=(b); echo hi > $x"])
def test_array_value_is_unknown(P, cmd):
    v = run(cmd, P)
    assert v == UNK and v.word == "$x"
