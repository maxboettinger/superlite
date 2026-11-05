"""Tests for coverage.py (category list, ## Coverage check, skeleton, CLI)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Import by path under a private name so an installed pytest `coverage` package is never shadowed.
_spec = importlib.util.spec_from_file_location("sl_coverage", SCRIPTS / "coverage.py")
cov = importlib.util.module_from_spec(_spec)
sys.modules["sl_coverage"] = cov
_spec.loader.exec_module(cov)

HEAD = "## Coverage\n\n| Category | State | Basis |\n|---|---|---|\n"
NOTE = ("NOTE: no ## Coverage section; brainstorming's coverage pass writes it "
        "(sl coverage prints the table), or set **Coverage:** off")


def table(rows):
    return HEAD + "".join(f"| {a} | {b} | {c} |\n" for a, b, c in rows)


def full(state="settled", basis="spec 1", skip=(), override=None):
    override = override or {}
    rows = []
    for name, _ in cov.categories(root=Path("/nonexistent-root")):
        if name in skip:
            continue
        s, b = override.get(name, (state, basis))
        rows.append((name, s, b))
    return table(rows)


NR = Path("/nonexistent-root")


def chk(text, **kw):
    return cov.check(text, root=NR, **kw)


def test_categories_builtin():
    c = cov.categories(root=NR)
    assert len(c) == 14
    assert c[0] == ("Scope and success criteria", "what is in, what is out (non-goals), how success is measured")
    assert c[-1][0] == "Research unknowns"


def test_coverage_off():
    assert cov.coverage_off("**Coverage:** off\n") is True
    assert cov.coverage_off("**Coverage:** on\n") is False
    assert cov.coverage_off("Coverage: off") is False


def test_section_span():
    assert cov.section_span(["# P", "## Coverage", "| a | b | c |", "## Next"]) == (1, 3)
    assert cov.section_span(["```", "## Coverage", "```"]) is None
    assert cov.section_span(["### Coverage"]) is None
    assert cov.section_span(["## Coverage table", "x"]) == (0, 2)


def test_check_no_section_note():
    assert cov.check("# P\n") == ([], [NOTE])


def test_check_off():
    assert cov.check("**Coverage:** off\n") == ([], [])


def test_fenced_heading_ignored():
    assert cov.check("```\n## Coverage\n```\n") == ([], [NOTE])


def test_check_full_table_ok():
    assert chk(full()) == ([], [])


def test_check_missing_and_open():
    text = full(skip=("Persistence and migration",),
                override={"Error handling and recovery": ("open", "what if the file is corrupt?")})
    assert chk(text) == ([
        "COVERAGE: no row for 'Persistence and migration'; add it as settled, ruled, n/a, spike or open",
        "COVERAGE: 'Error handling and recovery' is open; ask it or rule it (what if the file is corrupt?)",
    ], [])


def test_check_bad_state_and_empty_basis():
    text = full(override={"Rollout": ("maybe", "x"), "Observability": ("settled", "")})
    assert chk(text)[0] == [
        "COVERAGE: 'Observability' is settled but gives no basis",
        "COVERAGE: 'Rollout' has state 'maybe'; use settled, ruled, n/a, spike or open",
    ]


def test_check_spike():
    text = full(override={"Research unknowns": ("spike", "S1")})
    assert chk(text, task_ids={"S1", "T1"})[0] == []
    assert chk(text, task_ids=None)[0] == []
    assert chk(text, task_ids={"T1"})[0] == ["COVERAGE: 'Research unknowns' is spike but names no task of this plan"]


def test_state_case_and_markup():
    text = full(skip=("UI states", "Rollout")) + "| **UI states** | N/A | CLI only |\n| `Rollout` | Ruled | Ruling: ship dark |\n"
    assert chk(text) == ([], [])


def test_escaped_pipe_cell():
    text = full(skip=("Rollout",)) + "| Rollout | ruled | Ruling: a \\| b |\n"
    assert chk(text) == ([], [])


def test_crlf_text():
    text = full(override={"Rollout": ("open", "q?")})
    assert chk(text.replace("\n", "\r\n")) == chk(text)
    assert chk(text.replace("\n", "\r\n"))[0] != []


def test_extras_file(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "coverage.md").write_text(
        "| Category | Asks about |\n|---|---|\n| Billing | invoices and refunds |\n", encoding="utf-8")
    c = cov.categories(root=tmp_path)
    assert len(c) == 15 and c[-1] == ("Billing", "invoices and refunds")
    assert cov.check(full(), root=tmp_path) == (
        ["COVERAGE: no row for 'Billing'; add it as settled, ruled, n/a, spike or open"], [])


def test_missing_source(tmp_path):
    none = tmp_path / "none.md"
    assert cov.check("## Coverage\n", root=NR, source=none) == ([f"COVERAGE: category list not found: {none}"], [])


def test_skeleton_round_trip():
    sk = cov.skeleton(root=NR)
    assert sk.splitlines()[0] == "| Category | State | Basis |"
    issues, notes = chk("## Coverage\n\n" + sk)
    assert len(issues) == 14 and all("is open" in i for i in issues) and notes == []


def test_cli(tmp_path, capsys):
    assert cov.main(["--root", str(NR)]) == 0
    assert capsys.readouterr().out.startswith("| Category | State | Basis |")
    f = tmp_path / "d.md"
    f.write_text(full(override={"Rollout": ("open", "when?")}), encoding="utf-8")
    assert cov.main(["check", str(f), "--root", str(NR)]) == 1
    assert "COVERAGE: 'Rollout' is open; ask it or rule it (when?)" in capsys.readouterr().out
    assert cov.main(["check", str(tmp_path / "gone.md")]) == 2
    assert "coverage: not found:" in capsys.readouterr().err
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "coverage.md").write_text(
        "| Category | Asks about |\n|---|---|\n| Billing | invoices and refunds |\n", encoding="utf-8")
    assert cov.main(["--root", str(tmp_path)]) == 0
    assert "| Billing | open | invoices and refunds |" in capsys.readouterr().out


def test_sl_coverage_runs():
    cp = subprocess.run(["bash", str(SCRIPTS / "sl"), "coverage"], capture_output=True, timeout=120, cwd=ROOT)
    assert cp.returncode == 0
    assert "| Category | State | Basis |" in cp.stdout.decode("utf-8")


def test_bom_text():
    assert chk("﻿" + full()) == ([], [])
    assert cov.coverage_off("﻿**Coverage:** off\n")
