import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

from guard_judge import Verdict, judge  # noqa: E402

UNK = Verdict("?", "?", "code")


def _mk(root):
    p = (root / "p").resolve()
    for d in ("src", "docs/plans", ".superlite/linux"):
        (p / d).mkdir(parents=True)
    (p / "src" / "x.py").write_text("x = 1\n")
    return p


@pytest.fixture
def P(tmp_path):
    return str(_mk(tmp_path))


def run(cmd, P, mode="active", cwd=None):
    return judge(cmd, cwd or P, P, mode)


@pytest.mark.parametrize("cmd", [
    "false && PWD=/tmp; echo hi > $PWD/src/x.py",
    "if false; then PWD=/tmp; fi; echo hi > $PWD/src/x.py",
    "for v in a; do PWD=/tmp; done | cat; echo hi > $PWD/src/x.py",
    "for v in a; do PWD=/tmp; done > $PWD/src/x.py",
    "false && CLAUDE_PROJECT_DIR=/tmp; echo hi > $CLAUDE_PROJECT_DIR/src/x.py",
])
def test_conditional_pwd_keeps_the_directory(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "false && X=.superlite/a; echo hi > $X",
    "if [ -e z ]; then X=.superlite/a; fi; echo hi > $X",
])
def test_conditional_env_name_is_unknown(P, cmd):
    v = run(cmd, P)
    assert v == UNK and v.word == "$X"


def test_conditional_home_and_ifs(P):
    v = run(f"false && HOME={P}; echo hi > ~/src/x.py", P)
    assert v is not None and v.rel == "src/x.py"
    assert run("false && IFS=x; X=.superlite/xsrc/x.py; rm $X", P) == UNK


@pytest.mark.parametrize("cmd", [
    "for t in a b; do f=.superlite/$t; echo hi > $f; done",
    "if true; then X=.superlite/a; echo hi > $X; fi",
    "while true; do X=.superlite/a; echo hi >> $X; done",
])
def test_first_assignment_known_inside_its_block(P, cmd):
    assert run(cmd, P) is None


@pytest.mark.parametrize("cmd", [
    "s=.superlite/a; while true; do echo hi > $s; s=src/x.py; done",
    "s=.superlite/a; until false; do echo hi > $s; s=src/x.py; done",
    "s=.superlite/a; if true; then while true; do echo hi > $s; s=src/x.py; done; fi",
])
def test_while_body_reassigns_after_use(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


def test_growing_loop_value_is_unknown(P):
    assert run("s=.superlite/a; while true; do echo hi > $s; s=$s/b; done", P) == UNK


def test_force_cond_registers_nothing(P):
    assert run("f() { :; }; D=.superlite; echo hi > $D/x", P) is None


@pytest.mark.parametrize("ns", [(10, 10), (5, 5, 5), (3, 3, 3, 3)])
def test_nested_literal_for_loops_are_not_walked_again(P, ns):
    names = "abcd"
    head = "".join(f"for {names[k]} in {' '.join(str(i) for i in range(n))}; do " for k, n in enumerate(ns))
    body = "echo hi > docs/" + "".join("$" + names[k] for k in range(len(ns))) + ".md; " + "done; " * len(ns)
    assert run(head + body, P) is None
