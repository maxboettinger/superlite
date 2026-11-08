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
    "while true; do sh; done <<EOF\nrm src/x.py\nEOF",
    "for v in a; do sh; done <<EOF\nrm src/x.py\nEOF",
    "while true; do sh; done <<< 'rm src/x.py'",
    "while sh; do :; done <<EOF\nrm src/x.py\nEOF",
    "while true; do source /dev/stdin; done <<EOF\nrm src/x.py\nEOF",
])
def test_done_heredoc_reaches_body(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "if true; then sh; fi <<EOF\nrm src/x.py\nEOF",
    "case a in a) sh;; esac <<EOF\nrm src/x.py\nEOF",
])
def test_fi_and_esac_heredoc_reach_body(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


def test_outer_block_heredoc_reaches_nested_body(P):
    v = run("while true; do for v in a; do sh; done; done <<EOF\nrm src/x.py\nEOF", P)
    assert v is not None and v.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "{ sh; echo; } <<EOF\nrm src/x.py\nEOF",
    "( sh ) <<EOF\nrm src/x.py\nEOF",
])
def test_group_and_subshell_heredoc(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "while true; do x=$(sh); done <<EOF\nrm src/x.py\nEOF",
    "while true; do (sh); done <<EOF\nrm src/x.py\nEOF",
])
def test_body_substitution_and_subshell_read_block_stdin(P, cmd):
    v = run(cmd, P)
    assert v is not None and v.rel == "src/x.py"


def test_piped_loop_body(P):
    v = run("printf 'rm src/x.py\\n' | while true; do sh; done", P)
    assert v == UNK and v.word == "program piped into sh"
    v = run("cat <<EOF | while true; do sh; done\nrm src/x.py\nEOF", P)
    assert v is not None and v.rel == "src/x.py"


def test_heredoc_script_and_block_docs_both_judged(P):
    v = run("cat > .superlite/s.py <<'A'\nimport os; os.remove('src/x.py')\nA\n"
            "while read l; do python3 .superlite/s.py; done <<EOF\ndata\nEOF", P)
    assert v is not None and v.rel == "src/x.py"


@pytest.mark.parametrize("cmd", [
    "while read l; do echo \"$l\" >> .superlite/log; done <<EOF\nsrc/x.py\nEOF",
    "for f in a b; do cat; done <<EOF\nhi\nEOF",
    "while read f; do sh -c 'echo hi'; done <<EOF\nrm src/x.py\nEOF",
    "while read l; do sh build.sh; done <<EOF\nrm src/x.py\nEOF",
])
def test_block_stdin_benign_passes(P, cmd):
    assert run(cmd, P) is None
