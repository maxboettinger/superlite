"""Plan.load: an unreadable or non-UTF-8 plan raises PlanError (exit 2), never a traceback."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from test_plan_tools import PLAN_TOOLS, SCRIPTS, run  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

from plan_tools import Plan, PlanError  # noqa: E402

needs_posix_user = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="chmod 000 does not block reads on Windows or as root",
)


@needs_posix_user
def test_unreadable_plan_is_plan_error(tmp_path):  # O(1)
    p = tmp_path / "plan.md"  # O(1)
    p.write_text("# plan\n", encoding="utf-8")  # O(1)
    p.chmod(0)  # O(1)
    try:  # O(1)
        with pytest.raises(PlanError) as info:  # O(1)
            Plan.load(str(p))  # O(1)
    finally:  # O(1)
        p.chmod(0o600)  # O(1)
    assert str(info.value).startswith(f"plan not readable: {p}")  # O(1)
    assert info.value.code == 2  # O(1)


def test_invalid_utf8_is_plan_error(tmp_path):  # O(1)
    p = tmp_path / "plan.md"  # O(1)
    p.write_bytes(b"# plan\n\xff\xfe\x80 broken\n")  # O(1)
    with pytest.raises(PlanError) as info:  # O(1)
        Plan.load(str(p))  # O(1)
    assert str(info.value).startswith(f"plan not readable: {p}")  # O(1)
    assert info.value.code == 2  # O(1)


def test_directory_is_plan_not_found(tmp_path):  # O(1)
    with pytest.raises(PlanError) as info:  # O(1)
        Plan.load(str(tmp_path))  # O(1)
    assert str(info.value) == f"plan not found: {tmp_path}"  # O(1)


@needs_posix_user
def test_cli_unreadable_plan_no_traceback(tmp_path):  # O(1)
    p = tmp_path / "plan.md"  # O(1)
    p.write_text("# plan\n", encoding="utf-8")  # O(1)
    p.chmod(0)  # O(1)
    try:  # O(1)
        cp = run(PLAN_TOOLS, "lint", "--plan", p)  # O(process)
    finally:  # O(1)
        p.chmod(0o600)  # O(1)
    assert cp.returncode == 2  # O(1)
    assert "Traceback" not in cp.err  # O(1)
