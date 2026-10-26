"""dispatch: a `- Ruling: skip T0` ledger line silences the synthesized Wave 0 line."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, run
from test_stable_split import DISPATCH
from test_wave0 import PY, WAVE0, plan

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402


def _dispatch(tmp_path, p, ledger):
    return run(DISPATCH, "--plan", p, "--pool", tmp_path / "pool.json", "--ledger", ledger, cwd=tmp_path).out


def test_t0_omitted_after_skip_ruling(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    run(WAVE0, "--plan", p, cwd=tmp_path)
    ledger = tmp_path / ".superlite" / "progress.md"
    ledger.parent.mkdir(exist_ok=True)
    ledger.write_text("- Ruling: skip T0 - plan rules no Wave 0 - cost: none\n", encoding="utf-8")
    out = _dispatch(tmp_path, p, ledger)
    assert "T0" not in out and out.strip()  # other lines stay


def test_t0_offered_without_ruling(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    run(WAVE0, "--plan", p, cwd=tmp_path)
    ledger = tmp_path / "l.md"
    ledger.write_text("- start abc\n", encoding="utf-8")
    assert _dispatch(tmp_path, p, ledger).splitlines()[0].startswith("T0 wave0")


def test_skip_t0_reader(tmp_path):
    f = tmp_path / "l.md"
    f.write_text("- Ruling: skip T0 - x - y\n", encoding="utf-8")
    assert dispatch.skip_t0(f) is True
    f.write_text("Ruling: skip T0 - x\n", encoding="utf-8")
    assert dispatch.skip_t0(str(f)) is True
    f.write_text("- Ruling: skip T1 - x\n- ruling: skip t0\n", encoding="utf-8")
    assert dispatch.skip_t0(f) is False
    assert dispatch.skip_t0(tmp_path / "missing.md") is False
