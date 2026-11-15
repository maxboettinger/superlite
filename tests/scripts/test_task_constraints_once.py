"""`sl task Tn` prints the plan's Global constraints only on request.

Every agent already holds them once: the slim and mini primes carry them, and a fleet brief renders them
through `task.render` (#635). The CLI repeated them on every call (about 4.5k characters a call in traced
runs), so it now prints a one-line pointer instead and `--constraints` brings the section back.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import plan_tools as pt  # noqa: E402
import task  # noqa: E402

HEAD = "# Plan\n**Tech stack:** Python\n\nGlobal constraints:\n- stdlib only.\n- No version edits.\n\n"
TASKS = "### T1 First\n**Owns:** a.py\n**Produces:** a.f() -> int\n\n### T2 Second\n**Owns:** b.py\n**Consumes:** a.f() -> int (T1)\n"


def _plan(tmp_path, text):
    f = tmp_path / "plan.md"
    f.write_text(text)
    return f


def test_cli_omits_constraints_by_default(tmp_path, capsys):
    f = _plan(tmp_path, HEAD + TASKS)
    assert task.main(["T2", "--plan", str(f)]) == 0
    out = capsys.readouterr().out
    assert "## Global constraints" not in out and "- stdlib only." not in out
    assert out.rstrip("\n").endswith(task.CONSTRAINTS_POINTER.format(tid="T2"))
    assert "## Consumed interfaces" in out


def test_cli_constraints_flag_prints_section_once(tmp_path, capsys):
    f = _plan(tmp_path, HEAD + TASKS)
    assert task.main(["T2", "--plan", str(f), "--constraints"]) == 0
    out = capsys.readouterr().out
    assert out.count("## Global constraints") == 1
    assert out.endswith("## Global constraints\n\n**Tech stack:** Python\nGlobal constraints:\n- stdlib only.\n- No version edits.\n")
    assert "--constraints" not in out


def test_cli_no_pointer_when_plan_has_no_constraints(tmp_path, capsys):
    f = _plan(tmp_path, "# Plan\n\n" + TASKS)
    assert task.main(["T1", "--plan", str(f)]) == 0
    out = capsys.readouterr().out
    assert "Global constraints" not in out


def test_render_keeps_constraints_by_default_and_drops_them_on_request():
    p = pt.Plan(HEAD + TASKS)
    assert task.render(p, "T1").count("## Global constraints") == 1  # fleet briefs render through here
    out = task.render(p, "T1", constraints=False)
    assert "## Global constraints" not in out and "- stdlib only." not in out


def test_pointer_is_not_a_heading_so_fleet_still_appends_constraints():
    line = task.CONSTRAINTS_POINTER.format(tid="T1")
    assert not re.search(r"^#{1,4}\s+Global constraints", line, re.I | re.M)  # fleet.with_constraints keys on the heading (#635)
