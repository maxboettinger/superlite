"""#550: the script tests' run() helpers pass the per-test SUPERLITE_HOME, and conftest sets a session home at import."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
IMPORT_HOME = os.environ.get("SUPERLITE_HOME")  # at import of this module, after conftest ran
import test_0_3_1_scripts as t031  # noqa: E402
import test_run_scripts as trs  # noqa: E402


def test_conftest_sets_a_session_home_at_import():
    assert IMPORT_HOME
    assert Path(IMPORT_HOME) != Path.home() / ".superlite"


def test_conftest_turns_the_machine_limit_off_per_test():
    assert os.environ["SUPERLITE_MACHINE_LIMIT"] == "0"


@pytest.mark.parametrize("mod", [t031, trs])
def test_run_helpers_pass_the_test_home(mod, monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw["env"])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "X"))
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    mod.run("anything")
    assert seen["SUPERLITE_HOME"] == str(tmp_path / "X")
