"""#550: the script tests' run() helpers pass the per-test SUPERLITE_HOME, and conftest sets a session home at import."""
import os
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


@pytest.mark.parametrize("mod", [t031, trs])
def test_run_helpers_pass_the_test_home(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "X"))
    script = Path(mod.SCRIPTS) / "_print_home_550.py"
    script.write_text("import os\nprint(os.environ['SUPERLITE_HOME'])\n", encoding="utf-8")
    try:
        r = mod.run("_print_home_550")
    finally:
        script.unlink()
    assert r.stdout.strip() == str(tmp_path / "X")
