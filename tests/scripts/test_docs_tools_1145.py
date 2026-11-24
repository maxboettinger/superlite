"""#1145: docs/tools.md names the per-tree synced interpreter of pt_review and probe_run; its quoted texts are the ones _pyrun.py prints."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
PYRUN = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "_pyrun.py").read_text(encoding="utf-8")
HEAD = "| `pt_review` and `probe_run` interpreter (#1145) |"


def row():
    rows = [i for i, line in enumerate(TOOLS) if line.startswith(HEAD)]
    assert len(rows) == 1, rows
    return rows[0]


def test_row_1145_follows_probe_run():
    i = row()
    assert TOOLS[i - 1].startswith("| `probe_run` |")
    assert TOOLS[i].endswith(" |") and TOOLS[i].count(" | ") == 1


def test_row_1145_quotes_pyrun():
    line = TOOLS[row()]
    for text in ("is the main checkout's environment, outside ", "'s own environment once: uv sync --frozen --project ",
                 "this check may import that folder's package, not ", "has no uv.lock for an environment of its own",
                 "uv is not on PATH for ", "(#1145)"):
        assert text in line, text
        assert text in PYRUN, text
    assert "`_pyrun.tree_python(root, prog)`" in line and "def tree_python(root, prog)" in PYRUN
    assert "at most 300 s" in line and "SYNC_TIMEOUT = 300" in PYRUN
