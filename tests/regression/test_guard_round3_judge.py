"""Guard round 3 (judge): an sl call is told by its real path, and a hard link to a code file is code."""
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from guard_judge import judge  # noqa: E402


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    for d in (".superlite", "docs/plans", "src"):
        (p / d).mkdir(parents=True)
    (p / "src" / "a.py").write_text("x = 1\n")
    return os.path.realpath(p)


def _v(proj, cmd, mode="active"):
    return judge(cmd, proj, proj, mode)


FAKE_DIR = ".superlite/subagent-driven-development/scripts"


@pytest.mark.parametrize("cmd", [
    f"{FAKE_DIR}/rm src/a.py",
    f"./{FAKE_DIR}/rm src/a.py",
    "/tmp/subagent-driven-development/scripts/rm src/a.py",
    "/tmp/subagent-driven-development/scripts/tee src/a.py",
    f"bash -s {FAKE_DIR}/x <<'EOF'\nrm src/a.py\nEOF",
    "sh -s /tmp/subagent-driven-development/scripts/x <<'EOF'\nrm src/a.py\nEOF",
])
def test_a_path_that_only_contains_the_scripts_folder_name_is_judged(proj, cmd):
    # the file may be planted by the coordinator; the judge cannot treat the name as an sl call
    v = _v(proj, cmd)
    assert v is not None and v.kind == "code", cmd


@pytest.mark.parametrize("cmd", [
    'bash "$SL" dispatch implementer t1',
    "$SL run_tests --fast tests/a.py",
    "${SL} run_tests --fast tests/a.py",
    f"{SCRIPTS}/sl run_tests --fast tests/a.py",
    f"bash {SCRIPTS}/sl run_tests --fast tests/a.py",
    f"sh {SCRIPTS}/../scripts/sl run_tests",
])
def test_a_real_sl_call_still_passes(proj, cmd):
    assert _v(proj, cmd) is None, cmd


def test_a_symlink_into_the_scripts_folder_from_outside_is_not_an_sl_call(proj, tmp_path):
    evil = tmp_path / "evil.sh"
    evil.write_text("rm src/a.py\n")
    (Path(proj) / ".superlite" / "sl").symlink_to(evil)
    assert _v(proj, "sh .superlite/sl ; rm src/a.py") is not None
    (Path(proj) / ".superlite" / "rm").symlink_to(evil)
    assert _v(proj, ".superlite/rm src/a.py") is not None


@pytest.mark.parametrize("mode", ["active", "human"])
@pytest.mark.parametrize("cmd", [
    "ln src/a.py .superlite/a",
    "ln src/a.py docs/plans/a.md",
    "cp -l src/a.py .superlite/a",
    "link src/a.py .superlite/a",
    "ln -t .superlite src/a.py",
])
def test_a_hard_link_to_a_code_file_blocks(proj, cmd, mode):
    assert _v(proj, cmd, mode) is not None, cmd


def test_a_write_through_an_existing_hard_link_blocks(proj):
    os.link(proj + "/src/a.py", proj + "/.superlite/a")
    for cmd in ("echo x >> .superlite/a", "tee .superlite/a", "rm .superlite/a"):
        v = _v(proj, cmd)
        assert v is not None and v.kind == "code", cmd


def test_a_file_with_one_link_in_the_run_folder_still_passes(proj):
    (Path(proj) / ".superlite" / "n.md").write_text("n")
    assert _v(proj, "echo x >> .superlite/n.md") is None
    assert _v(proj, "ln -s ../docs/plans/x.md .superlite/b.md") is None
    assert _v(proj, "ln docs/plans/x.md docs/plans/y.md") is None


def test_hard_link_check_does_not_apply_when_not_enforcing(proj):
    os.link(proj + "/src/a.py", proj + "/src/b.py")
    assert judge("echo x >> src/b.py", proj, proj, "off") is None
