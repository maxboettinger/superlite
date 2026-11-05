"""T12: re.split/sub/subn take count and flags as keyword arguments, never positionally."""
from __future__ import annotations

import ast
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402


def test_wave0_header_without_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert plan_tools.Plan("**Wave0:** none\n## T1\n").header_wave0_off() is True


def test_no_positional_re_count_or_flags():
    files = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    bad = []
    for f in files:
        try:
            tree = ast.parse((ROOT / f).read_text(encoding="utf-8"), f)
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            continue  # deleted-but-tracked file or an intentionally broken fixture
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "re"):
                continue
            n = len(node.args)
            if (fn.attr == "split" and n > 2) or (fn.attr in ("sub", "subn") and n > 3):
                bad.append(f"{f}:{node.lineno} re.{fn.attr} with {n} positional arguments")
    assert not bad, "\n".join(bad)
