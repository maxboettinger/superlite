"""pt_review pix v2: import roots, docs-only seam, bytes-safe adapter, seam usage text."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

PKG = "config/skills/reviewing-periods/scripts"


def hyphen_proj(tmp_path: Path, key: bool = True) -> Path:
    p = tmp_path / "hy"
    pk = p / PKG / "review"
    pk.mkdir(parents=True)
    (pk / "__init__.py").write_text("")
    (pk / "shell.py").write_text("def run_json(argv: list[str]) -> dict:\n    return {}\n")
    (p / ".superlite").mkdir()
    if key:
        (p / ".superlite" / "test-cmd.json").write_text(json.dumps({"test": "pytest", "pythonpath": [PKG]}))
    (p / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1 --> T2\n```\n\n"
        f"### T1 shell · Complexity 2\n**Owns:** {PKG}/review/shell.py\n"
        "**Produces:** review.shell.run_json(argv: list[str]) -> dict\n\n"
        "### T2 use · Complexity 2\n**Owns:** x.md\n"
        "**Consumes:** review.shell.run_json(argv: list[str]) -> dict (T1)\n\n## Review Focus\n- x\n")
    return p


def contract(p: Path, *extra: str) -> int:
    return pt_review.main(["contract", "--plan", str(p / "plan.md"), "--root", str(p), *extra])


def test_contract_hyphen_package(tmp_path, capsys):
    p = hyphen_proj(tmp_path)
    assert contract(p) == 0
    out = capsys.readouterr().out
    assert "PASS" in out and "not found" not in out


def test_contract_hyphen_package_derived(tmp_path, capsys):
    p = hyphen_proj(tmp_path, key=False)
    assert contract(p) == 0
    assert "PASS" in capsys.readouterr().out


def test_docs_producer_seam_quiet(tmp_path, capsys):
    p = tmp_path / "docs"
    (p / "config/skills/x/references").mkdir(parents=True)
    (p / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT9 --> T10a\n```\n\n"
        "### T9 skill · Complexity 1\n**Owns:** config/skills/x/SKILL.md\n"
        '**Produces:** SKILL.md sections "Voice"\n\n'
        "### T10a refs · Complexity 1\n**Owns:** config/skills/x/references/a.md\n"
        '**Consumes:** SKILL.md sections "Voice" (T9)\n\n## Review Focus\n- x\n')
    (p / "config/skills/x/SKILL.md").write_text("# X\n\n## Voice\n")
    contract(p, "--seam", "T9,T10a")
    assert "not declared" not in capsys.readouterr().out


def make_adapter(tmp_path: Path, run: str, roots: list[str] | None = None):
    plan = pt_review.parse_plan(_plan(tmp_path, run))
    pt_review.IMPORT_ROOTS[:] = roots or []
    try:
        src = pt_review.build_adapter(plan, tmp_path / "adapter.py", tmp_path)
    finally:
        pt_review.IMPORT_ROOTS[:] = []
    (tmp_path / "adapter.py").write_text(src)
    spec = importlib.util.spec_from_file_location("adapter_x", tmp_path / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, src


def _plan(tmp_path: Path, run: str) -> Path:
    f = tmp_path / "ap.md"
    f.write_text(f"# p\n\n### T1 a · Complexity 1\n**Owns:** a.py\n\n**Probe entry:** run={run}\n\n## Review Focus\n- x\n")
    return f


def test_adapter_run_bytes_stdin(tmp_path):
    mod, _ = make_adapter(tmp_path, "python -c \"import sys; sys.stdin.buffer.read(); print('ok')\"")
    assert mod.run((), b"\xff\xfe") == (0, "ok\n", "")


def test_adapter_run_str_stdin_unchanged(tmp_path):
    mod, _ = make_adapter(tmp_path, "python -c \"import sys; print(sys.stdin.read().upper())\"")
    assert mod.run((), "abc") == (0, "ABC\n", "")


def test_adapter_has_import_roots(tmp_path):
    mod, src = make_adapter(tmp_path, "python -c \"import os; print(os.environ['PYTHONPATH'])\"", [PKG])
    assert str(mod.ROOT / PKG) in sys.path
    rc, out, _ = mod.run()
    assert str(mod.ROOT / PKG) in out
    sys.path.remove(str(mod.ROOT / PKG))


def test_seam_error_names_comma_form(tmp_path, capsys):
    p = hyphen_proj(tmp_path)
    assert contract(p, "--seam", "T1") == 2
    assert "Ta,Tb" in capsys.readouterr().err


def test_module_name_deepest_import_root(tmp_path):
    p = hyphen_proj(tmp_path)
    pt_review.IMPORT_ROOTS[:] = [PKG]
    try:
        assert pt_review.module_name(p, p / PKG / "review" / "shell.py") == "review.shell"
        assert pt_review.module_name(p, p / PKG / "review" / "__init__.py") == "review"
    finally:
        pt_review.IMPORT_ROOTS[:] = []
    assert pt_review.module_name(p, p / PKG / "review" / "shell.py").endswith("review.shell")
    assert pt_review.module_name(p, p / PKG / "review" / "shell.py").startswith("config.")
