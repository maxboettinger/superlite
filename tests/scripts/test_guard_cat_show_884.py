"""#884: `cat F > x` and `git show REV:F > x` give x the copied text; #883: a link made by code drops recorded texts."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

from guard_judge import judge  # noqa: E402

GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
LINK = "python3 -c 'import os; os.symlink(\"y.sh\", \".superlite/scratch/l\")'"
Y = "cat > .superlite/scratch/y.sh <<'E'\necho hi\nE\n"


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "p"
    (p / ".superlite" / "scratch").mkdir(parents=True)
    (p / "tools").mkdir()
    (p / "tools" / "ok.sh").write_text("echo hi\n")
    (p / "tools" / "bad.sh").write_text("rm -rf src\n")
    (p / "tools" / "defs.sh").write_text("A=1\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "add", "tools"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   check=True, env=GIT_ENV)
    (p / ".superlite" / "m.py").write_text("print(1)\n")
    (p / ".superlite" / "scratch" / "c0.sh").write_text("echo hi\n")
    return str(p)


def _j(p, cmd):
    return judge(cmd, p, p, "active", (p + "/.superlite",))


@pytest.mark.parametrize("cmd", [
    "cat tools/ok.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat tools/ok.sh tools/defs.sh > .superlite/scratch/c.sh && bash .superlite/scratch/c.sh",
    "cat -- tools/ok.sh >| .superlite/scratch/c.sh; sh .superlite/scratch/c.sh",
    "cat .superlite/m.py > .superlite/scratch/m.py; python3 .superlite/scratch/m.py",
    "cat > .superlite/scratch/h.sh <<'E'\necho a\nE\ncat tools/ok.sh >> .superlite/scratch/h.sh; bash .superlite/scratch/h.sh",
    "cat > .superlite/scratch/h.sh <<'E'\necho a\nE\ncat .superlite/scratch/h.sh > .superlite/scratch/k.sh; bash .superlite/scratch/k.sh",
    "git show HEAD:tools/ok.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "git show HEAD:./tools/ok.sh > .superlite/scratch/g.sh && sh .superlite/scratch/g.sh",
    Y + "python3 -c 'print(1)'; bash .superlite/scratch/y.sh",
])
def test_copied_text_is_judged(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("cmd", [
    "cat tools/bad.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "git show HEAD:tools/bad.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "cat -n tools/ok.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat tools/ok.sh - > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat tools/*.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    'cat "$F" > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh',
    "cat tools/ok.sh > .superlite/scratch/c.sh > .superlite/scratch/d.sh; bash .superlite/scratch/d.sh",
    "cat tools/ok.sh <<< 'x' > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat tools/ok.sh > .superlite/scratch/c.sh; echo 'rm -rf src' >> .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat tools/ok.sh >> .superlite/scratch/new.sh; bash .superlite/scratch/new.sh",
    "cat() { echo 'rm -rf src'; }; cat tools/ok.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
    "cat .superlite/scratch/c0.sh > .superlite/scratch/c0.sh; bash .superlite/scratch/c0.sh",
    "git show --textconv HEAD:tools/ok.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "git status; git show HEAD:tools/ok.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "GIT_DIR=.git git show HEAD:tools/ok.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "git show HEAD:tools/nope.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "git show HEAD:tools > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    "git show HEAD > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh",
    Y + LINK + "; echo 'rm -rf src' > .superlite/scratch/l; bash .superlite/scratch/y.sh",
    Y + "node -e \"require('fs').symlinkSync('y.sh', '.superlite/scratch/l')\"; bash .superlite/scratch/y.sh",
    LINK + "; " + Y + "bash .superlite/scratch/y.sh",
    Y + "python3 - <<'P'\nimport os\nos.symlink('y.sh', '.superlite/scratch/l')\nP\nbash .superlite/scratch/y.sh",
    LINK + "; cat tools/ok.sh > .superlite/scratch/c.sh; bash .superlite/scratch/c.sh",
])
def test_unsure_text_blocks(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code"


def test_git_show_text_is_not_read_after_an_interpreter_ran_git(proj):
    cmd = ("python3 -c \"import subprocess; subprocess.run(['git', 'fetch'])\"; "
           "git show HEAD:tools/ok.sh > .superlite/scratch/g.sh; bash .superlite/scratch/g.sh")
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code"
