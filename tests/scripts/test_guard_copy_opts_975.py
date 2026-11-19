"""#975: an option value after the copy operands is no destination."""
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
    for d in (".superlite/scratch", ".superlite/a", ".superlite/b", "tools"):
        (p / d).mkdir(parents=True)
    (p / "tools" / "defs.sh").write_text("A=1\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "add", "tools"], check=True, env=GIT_ENV)
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
                   check=True, env=GIT_ENV)
    (p / ".superlite" / "a" / "evil.sh").write_text("rm -rf src\n")
    (p / ".superlite" / "a" / "ok.sh").write_text("echo hi\n")
    (p / ".superlite" / "a" / "n.md").write_text("# n\n")
    (p / ".superlite" / "scratch" / "evil.sh").write_text("echo stale\n")
    (p / ".superlite" / "scratch" / "run.sh").write_text("echo hi\n")
    return str(p)


def _j(p, cmd):
    return judge(cmd, p, p, "active", (p + "/.superlite",))



EVIL = "; bash .superlite/scratch/evil.sh"


@pytest.mark.parametrize("cmd", [
    "rsync -a .superlite/a/ .superlite/scratch/ --exclude zz" + EVIL,
    "cp .superlite/a/*.sh .superlite/scratch/ -S .bak" + EVIL,
    "mv .superlite/a/*.sh .superlite/scratch/ --suffix .bak" + EVIL,
    "rsync .superlite/a/ .superlite/scratch/ -a --filter 'P x'" + EVIL,
])
def test_value_after_operands_is_no_destination(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and "scratch/evil.sh" in v.word


@pytest.mark.parametrize("cmd", [
    "cp -S .bak .superlite/a/*.sh .superlite/scratch/" + EVIL,
    "install -m 755 .superlite/a/evil.sh .superlite/scratch/" + EVIL,
])
def test_value_before_operands_still_read(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and "scratch/evil.sh" in v.word


def test_option_after_operand_counts_every_operand(proj):
    v = _j(proj, "cp .superlite/a/ok.sh .superlite/scratch/evil.sh --unknown-flag zz" + EVIL)
    assert v is not None and v.kind == "code"


@pytest.mark.parametrize("cmd", [
    "cp .superlite/a/ok.sh .superlite/scratch/ok.sh; bash .superlite/scratch/ok.sh",
    "cp -f .superlite/a/ok.sh .superlite/scratch/ok.sh; bash .superlite/scratch/ok.sh",
    "rsync -a --exclude zz .superlite/a/ .superlite/b/; bash .superlite/scratch/run.sh",
    "cp .superlite/a/ok.sh .superlite/b/ -t .superlite/b/; bash .superlite/scratch/run.sh",
])
def test_reads_that_stay_passing(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("opt", ["-Sbat", "-Stxt"])
def test_suffix_value_with_t_is_no_target_directory(proj, opt):
    import guard_judge
    from types import SimpleNamespace

    w = ["cp", opt, ".superlite/a/evil.sh", ".superlite/scratch/run.sh"]
    c = SimpleNamespace(inn=[proj])
    dst = proj + "/.superlite/scratch/run.sh"
    st = SimpleNamespace(shared={"copied": [], "scripts": {dst: "echo hi\n"}, "wrote": set()}, made=set())
    guard_judge._copy_reach(w, [False] * 4, c, st, "cp")
    assert st.shared["copied"] == []  # -S owns "bat": no target folder, so no copy lands in a made-up one
    guard_judge._copy_text(w, [False] * 4, c, st, set(), {})
    assert dst not in st.shared["scripts"] or st.shared["scripts"][dst] is None  # the stale text is dropped
