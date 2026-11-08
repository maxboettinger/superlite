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


@pytest.mark.parametrize("mode", ["idle", "active"])
def test_glob_value_protects_in_every_mode(P, mode):
    v = run("X=.superlite/orch*; echo hi > $X", P, mode)
    assert v is not None and v.kind == "protected"


def test_glob_value_protects_rm_quoted(P):
    v = run('X=.superlite/orch*; rm "$X"', P)
    assert v is not None and v.kind == "protected"


def test_glob_value_is_a_glob_target(P):
    v = run("X='src/*.py'; echo hi > $X", P)
    assert v is not None and v.kind == "code"
    assert run("X='.superlite/*.md'; cat a > $X", P) is None


@pytest.mark.parametrize("cmd", ["X='.superlite/a src/x.py'; rm $X", "X='.superlite/a src/x.py'; rm \"\"$X"])
def test_whitespace_value_is_unknown(P, cmd):
    v = run(cmd, P)
    assert v == UNK and v.word == "$X"


@pytest.mark.parametrize("cmd", ["C='rm -f'; $C src/x.py", "X='/bin/r?'; $X src/x.py"])
def test_command_word_value_is_read(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py" and v.kind == "code"


@pytest.mark.parametrize("cmd", ['CMD=\'rm src/x.py\'; bash -c "$CMD"', 'CMD=\'rm src/x.py\'; eval "$CMD"'])
def test_command_text_values_still_walked(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


def test_custom_ifs_splits_values(P):
    assert run("IFS=x; X=.superlite/xsrc/x.py; rm $X", P) == UNK
    v = run("IFS=/; echo hi > $CLAUDE_PROJECT_DIR/.superlite/a", P)
    assert v is not None and v.kind == "code"
    assert run("IFS=; X='.superlite/a b'; echo hi > $X", P) is None


def test_project_path_with_space_still_passes(tmp_path):
    p = (tmp_path / "my p").resolve()
    (p / ".superlite").mkdir(parents=True)
    P = str(p)
    assert run('echo hi > "$CLAUDE_PROJECT_DIR/.superlite/a"', P) is None
    assert run('cd "$CLAUDE_PROJECT_DIR/.superlite" && echo hi > "$PWD/a"', P) is None


def test_plain_values_still_pass(P):
    assert run("X=.superlite/a; echo hi > $X", P) is None
    assert run("D=.superlite; cp f $D/x", P) is None


def test_tilde_plus_is_pwd(P):
    v = run("echo hi > ~+/src/x.py", P)
    assert v is not None and v.rel == "src/x.py"
    v = run(f"cd {P}/src; echo hi > ~+/x.py", P)
    assert v is not None and v.rel == "src/x.py"


def test_tilde_minus_is_oldpwd(P):
    v = run("cd /tmp; echo hi > ~-/src/x.py", P)
    assert v is not None and v.kind == "code"
    assert run(f"OLDPWD={P}/.superlite; echo hi > ~-/a", P) is None


def test_home_assignment_moves_tilde(P):
    v = run(f"HOME={P}; echo hi > ~/src/x.py", P)
    assert v is not None and v.rel == "src/x.py"
    v = run(f"HOME={P}; [ -e z ] && HOME=/tmp; echo hi > ~/src/x.py", P)
    assert v is not None and v.rel == "src/x.py"


def test_tilde_user_is_unknown(P):
    v = run("cd /tmp; echo hi > ~nosuchuser/x", P)
    assert v == UNK and v.word == "~nosuchuser/x"


def test_prefixed_read_clobbers(P):
    assert run("X=.superlite/a; IFS= read -r X; echo hi > $X", P) == UNK


def test_pwd_follows_the_chain(P):
    v = run("cd .superlite && echo hi > $PWD/../src/x.py", P)
    assert v is not None and v.rel == "src/x.py"


def test_cd_resets_assigned_pwd(P):
    v = run(f"PWD=/tmp; cd {P}; echo hi > $PWD/src/x.py", P)
    assert v is not None and v.rel == "src/x.py"
