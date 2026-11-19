"""#883: a script a glob, unknown-name or tree copy of this Bash call may have written runs as an unknown target."""
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


@pytest.mark.parametrize("cmd,word", [
    ("cp .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/new.sh", "scratch/new.sh"),
    ("cp .superlite/a/*.sh .superlite/scratch; sh .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/EVIL.sh", "scratch/EVIL.sh"),
    ("mv .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -f .superlite/a/* .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp .superlite/a/e?il.sh .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ('cp "$S" .superlite/scratch/; bash .superlite/scratch/evil.sh', "scratch/evil.sh"),
    ("rsync -a .superlite/a/ .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -r .superlite/a .superlite/scratch/; bash .superlite/scratch/a/evil.sh", "scratch/a/evil.sh"),
    ("cp -r .superlite/a .superlite/scratch/new; bash .superlite/scratch/new/evil.sh", "scratch/new/evil.sh"),
    ("install -m 755 .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp .superlite/a/*.sh .superlite/scratch/ && bash -c 'bash .superlite/scratch/evil.sh'", "scratch/evil.sh"),
    ("rm -rf .superlite/b; cp -r .superlite/a .superlite/b; bash .superlite/b/evil.sh", "b/evil.sh"),
])
def test_run_after_a_copy_of_unread_names_is_unknown(proj, cmd, word):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and word in v.word


@pytest.mark.parametrize("cmd", [
    "cp .superlite/a/*.md .superlite/scratch/; bash .superlite/scratch/run.sh",
    "cp .superlite/a/ok.sh .superlite/scratch/; bash .superlite/scratch/ok.sh",
    "cp .superlite/a/*.sh .superlite/b/; bash .superlite/scratch/run.sh",
    "cp -r .superlite/a .superlite/scratch/; bash .superlite/scratch/run.sh",
    "cp .superlite/a/*.sh .superlite/scratch/; bash tools/defs.sh",
    "rsync -a .superlite/a/ .superlite/b/; bash .superlite/scratch/run.sh",
    "cat > .superlite/scratch/y.sh <<'E'\necho hi\nE\nrsync -a .superlite/a/ .superlite/b/; bash .superlite/scratch/y.sh",
])
def test_runs_the_copy_cannot_reach_keep_their_reading(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("cmd", [
    "cat > .superlite/scratch/y.sh <<'E'\necho hi\nE\nrsync -a --link-dest=../a .superlite/a/ .superlite/b/; bash .superlite/scratch/y.sh",
    "cat > .superlite/scratch/y.sh <<'E'\necho hi\nE\nrsync -a --link-dest ../a .superlite/a/ .superlite/b/; bash .superlite/scratch/y.sh",
])
def test_rsync_link_dest_drops_recorded_text(proj, cmd):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and "scratch/y.sh" in v.word


def test_block_names_the_way_out(proj):
    v = _j(proj, "cp .superlite/a/*.sh .superlite/scratch/; bash .superlite/scratch/evil.sh")
    assert "copy it by its literal name" in v.word


@pytest.mark.parametrize("cmd,word", [
    ("cp -t .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp --target-directory=.superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp --target-directory .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -t.superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -rt .superlite/scratch .superlite/a; bash .superlite/scratch/a/evil.sh", "scratch/a/evil.sh"),
    ("cp -t .superlite/scratch .superlite/a/evil.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -t .superlite/scratch/ .superlite/a/evil.sh .superlite/a/ok.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("install -t .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("mv -t .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp -T .superlite/a/*.sh .superlite/scratch/evil.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
])
def test_target_directory_copy_counts_as_written(proj, cmd, word):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and word in v.word


@pytest.mark.parametrize("cmd", [
    "cp -t .superlite/scratch .superlite/a/*.md; bash .superlite/scratch/run.sh",
    "cp -t .superlite/b .superlite/a/*.sh; bash .superlite/scratch/run.sh",
])
def test_target_directory_copy_cannot_reach_keeps_reading(proj, cmd):
    assert _j(proj, cmd) is None


@pytest.mark.parametrize("cmd,word", [
    ("cp --t .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp --ta .superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp --ta=.superlite/scratch .superlite/a/*.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
])
def test_short_target_directory_prefix_counts_as_written(proj, cmd, word):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and word in v.word


@pytest.mark.parametrize("cmd,word", [
    ("cp --preserve=mode .superlite/a/evil.sh .superlite/scratch/; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
    ("cp --preserve=mode .superlite/a/evil.sh .superlite/scratch/new.sh; bash .superlite/scratch/new.sh", "scratch/new.sh"),
    ("cp -T .superlite/a/evil.sh .superlite/scratch/evil.sh; bash .superlite/scratch/evil.sh", "scratch/evil.sh"),
])
def test_one_file_copy_with_a_long_option_counts_as_written(proj, cmd, word):
    v = _j(proj, cmd)
    assert v is not None and v.kind == "code" and word in v.word


def test_one_file_copy_with_a_long_option_cannot_reach_keeps_reading(proj):
    assert _j(proj, "cp --preserve=mode .superlite/a/ok.sh .superlite/scratch/; bash .superlite/scratch/run.sh") is None


Y = "cat > .superlite/scratch/y.sh <<'E'\necho hi\nE\n"
THROUGH = "rsync -a .superlite/a/ .superlite/b/; echo 'rm -rf src' > .superlite/b/l; bash .superlite/scratch/y.sh"


def test_rsync_a_of_a_folder_with_a_symlink_drops_recorded_text(proj):
    os.symlink("../scratch/y.sh", os.path.join(proj, ".superlite", "a", "l"))
    v = _j(proj, Y + THROUGH)
    assert v is not None and v.kind == "code" and "scratch/y.sh" in v.word


def test_rsync_a_of_a_folder_without_a_symlink_keeps_reading(proj):
    assert _j(proj, Y + THROUGH) is None


@pytest.mark.parametrize("cmd", [
    "cp -r .superlite/a .superlite/b/",
    "cp -a .superlite/a/l .superlite/b/l",
    "cp -P .superlite/a/l .superlite/b/l",
    "cp -R .superlite/a/* .superlite/b/",
    "rsync -l .superlite/a/l .superlite/b/",
])
def test_symlink_keeping_copy_of_a_symlink_source_drops_recorded_text(proj, cmd):
    os.symlink("../scratch/y.sh", os.path.join(proj, ".superlite", "a", "l"))
    v = _j(proj, Y + cmd + "; echo 'rm -rf src' > .superlite/b/l; bash .superlite/scratch/y.sh")
    assert v is not None and v.kind == "code" and "scratch/y.sh" in v.word


_MK = "#!/usr/bin/env python3\nimport os\nos.symlink('s.py', '.superlite/scratch/l.py')\n"
_S = "print(1)\n"
_PRE = f"cat > .superlite/scratch/s.py <<'E1'\n{_S}E1\ncat > .superlite/scratch/m.py <<'E2'\n{_MK}E2\n"
_POST = "\nprintf 'import shutil\\nshutil.rmtree(\"src\")\\n' > .superlite/scratch/l.py\npython3 .superlite/scratch/s.py"


@pytest.mark.parametrize("run", [
    "python3 .superlite/scratch/m.py",
    "./.superlite/scratch/m.py",
    "uv run .superlite/scratch/m.py",
])
def test_link_made_by_a_script_file_drops_recorded_texts(proj, run):
    v = _j(proj, _PRE + run + _POST)
    assert v is not None and v.kind == "code" and "scratch/s.py" in v.word


@pytest.mark.parametrize("run", [
    "python3 .superlite/scratch/m.py",
    "./.superlite/scratch/m.py",
])
def test_script_file_without_a_link_keeps_recorded_texts(proj, run):
    pre = _PRE.replace("os.symlink('s.py', '.superlite/scratch/l.py')", "print('no link')")
    assert _j(proj, pre + run + _POST) is None
