"""#780: a script copied in the same Bash call is judged by its source's text; a later write drops a heredoc's text;
`$(seq ...)` and numeric `{a..b}` for-loop words are read."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

from guard_judge import judge  # noqa: E402

GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "p"
    (p / ".superlite" / "scratch").mkdir(parents=True)
    (p / "tools").mkdir()
    (p / "tools" / "defs.sh").write_text("A=1\nf() { echo hi; }\n# end\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "add", "tools/defs.sh"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   check=True, env=GIT_ENV)
    (p / ".superlite" / "m.py").write_text("print(1)\n")
    (p / ".superlite" / "bad.py").write_text("open('src/a.py', 'w').write('x')\n")
    (p / ".superlite" / "bad.sh").write_text("rm -rf src\n")
    return str(p)


def _j(p, cmd):
    return judge(cmd, p, p, "active", (p + "/.superlite",))


@pytest.mark.parametrize("cmd", [
    'mkdir -p .superlite/scratch; cp .superlite/m.py .superlite/scratch/m.py; python3 .superlite/scratch/m.py "$PWD"',
    "cp .superlite/m.py .superlite/scratch/ && python3 .superlite/scratch/m.py",
    "cp -f .superlite/m.py .superlite/scratch/m2.py && python3 .superlite/scratch/m2.py",
    "mv .superlite/m.py .superlite/scratch/m3.py; python3 .superlite/scratch/m3.py",
    "cp tools/defs.sh .superlite/scratch/d.sh; bash .superlite/scratch/d.sh",
    "cat > .superlite/scratch/x.sh <<'E'\necho hi\nE\ncp tools/defs.sh .superlite/scratch/x.sh; bash .superlite/scratch/x.sh",
])
def test_copied_script_is_judged_by_its_source_text(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("cmd", [
    "cp .superlite/bad.py .superlite/scratch/b.py; python3 .superlite/scratch/b.py",
    "cp .superlite/bad.sh .superlite/scratch/b.sh && bash .superlite/scratch/b.sh",
    "mv .superlite/bad.sh .superlite/scratch/; sh .superlite/scratch/bad.sh",
    "cat > .superlite/scratch/x.sh <<'E'\necho hi\nE\ncp .superlite/bad.sh .superlite/scratch/x.sh; bash .superlite/scratch/x.sh",
])
def test_copied_writer_blocks(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code"


@pytest.mark.parametrize("cmd", [
    'cp "$X" .superlite/scratch/m.py; python3 .superlite/scratch/m.py',
    "echo 'rm -rf src' > .superlite/a.sh; cp .superlite/a.sh .superlite/scratch/a.sh; bash .superlite/scratch/a.sh",
    "cp .superlite/bad.py .superlite/m.py .superlite/scratch/; python3 .superlite/scratch/m.py",
    "cp .superlite/missing.py .superlite/scratch/n.py; python3 .superlite/scratch/n.py",
])
def test_unreadable_copy_stays_unknown(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.rel == "?"


@pytest.mark.parametrize("write", [
    "echo 'rm -rf src' > .superlite/scratch/x.sh",
    "printf 'rm -rf src\\n' >> .superlite/scratch/x.sh",
    "sed -i.bak 's/hi/x/' .superlite/scratch/x.sh",
])
def test_later_write_drops_the_heredoc_text(proj, write):
    cmd = f"cat > .superlite/scratch/x.sh <<'E'\necho hi\nE\n{write}; bash .superlite/scratch/x.sh"
    assert _j(proj, cmd) is not None


def test_heredoc_script_alone_still_passes(proj):
    assert _j(proj, "cat > .superlite/scratch/x.sh <<'E'\necho hi\nE\nbash .superlite/scratch/x.sh") is None


@pytest.mark.parametrize("words", ["$(seq 1 40)", "$(seq 3)", "$(seq 2 2 10)", "{1..3}", "{01..12}", "{5..1}"])
def test_numeric_loop_words_bind_known_values(proj, words):
    out = os.path.dirname(proj) + "/sp"
    assert _j(proj, f"for i in {words}; do printf x > {out}/t$i; done") is None


def test_numeric_loop_into_the_project_names_the_file(proj):
    v = _j(proj, "for i in $(seq 1 3); do printf x > src/t$i.py; done")
    assert v is not None and v.rel == "src/t1.py"


@pytest.mark.parametrize("pre,words", [
    ("", "$(seq 1 100)"),
    ("", "$(seq 1 0.5 3)"),
    ("", "$(seq 1 0 3)"),
    ("", '"$(seq 1 3)"'),
    ("", "$(seq -w 1 3)"),
    ("", "{1..100}"),
    ("seq() { echo ../../src/a; }; ", "$(seq 1 3)"),
    ("alias seq='echo ../../src/a'; ", "$(seq 1 3)"),
    ("PATH=/tmp/x:$PATH; ", "$(seq 1 3)"),
    ("IFS=1; ", "$(seq 1 3)"),
])
def test_unreadable_loop_words_stay_unknown(proj, pre, words):
    out = os.path.dirname(proj) + "/sp"
    assert _j(proj, f"{pre}for i in {words}; do printf x > {out}/t$i; done") is not None
