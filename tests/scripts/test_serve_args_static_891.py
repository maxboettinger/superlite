"""#891: serve= arguments pt_review is certain to refuse fail plan lint, with the runtime's reasons."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_plan_edges_probe_stack_491_496 import lint, plan, task

import pt_review  # noqa: E402

TAIL = "write literals, names of pkg.server and calls of the project's own code"
STD = "{0} is imported from the standard library ({1}), not the project's own code"


@pytest.mark.parametrize("src, want", [
    ("Workbook(), port=0", None),
    ("1, 'a', [1, 2], {'k': (1,)}, *ARGS, **KW", None),
    ("cfg.Settings(debug=True)", None),
    ("lambda: 1", "Lambda"),
    ("x[0]", "Subscript"),
    ("f()()", "callee Call"),
    ("a + b", "BinOp"),
    ("{**d}", "dict ** entry"),
    ("__import__('os')", "name '__import__'"),
    ("obj.__class__", "attribute '__class__'"),
    ("f'x{y}'", "JoinedStr"),
    ("-1, 2.5", None),
])
def test_static_shapes(src, want):
    assert pt_review.serve_args_problem("pkg.server.create_server", src) == want


def test_static_shapes_parse_error():
    assert pt_review.serve_args_problem("pkg.server.create_server", "1, (")


def test_static_module_names(tmp_path):
    mod = tmp_path / "server.py"
    mod.write_text("from pathlib import Path\nfrom pkg.model import Workbook\nimport os\nDEFAULT = 3\n"
                   "def create_server(wb, port=0):\n    pass\n", encoding="utf-8")
    prob = lambda src, m=mod: pt_review.serve_args_problem("pkg.server.create_server", src, m)  # noqa: E731
    assert prob("Path('x')") == STD.format("Path", "pathlib")
    assert prob("os.getcwd()") == STD.format("os", "os")
    assert prob("Workbook()") is None
    assert prob("DEFAULT") is None
    assert prob("dict(a=1)") == "name 'dict'"
    assert prob("Missing()") == "name 'Missing'"
    assert prob("requests.get('u')") == "name 'requests'"
    star = tmp_path / "star.py"
    star.write_text("from x import *\n", encoding="utf-8")
    assert prob("Missing()", star) is None
    assert prob("Missing()", tmp_path / "none.py") is None
    assert prob("lambda: 1", tmp_path / "none.py") == "Lambda"


def serve_plan(tmp_path, entry):
    return plan(tmp_path, [task("T1", "pkg/server.py, pkg/__init__.py, tests/test_server.py", probe=f"serve={entry}")])


def test_lint_probe_serve_args(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "server.py").write_text("from pathlib import Path\nfrom pkg.model import Workbook\n"
                                   "def create_server(wb=None, port=0):\n    pass\n", encoding="utf-8")
    entry = 'pkg.server.create_server(Path("x"))'
    out = lint(serve_plan(tmp_path, entry))
    assert f"PROBE: serve={entry} arguments: {STD.format('Path', 'pathlib')}; {TAIL}" in out
    assert "PROBE: serve=pkg.server.create_server(Workbook())" not in lint(serve_plan(tmp_path, "pkg.server.create_server(Workbook())"))
    assert "arguments:" not in lint(serve_plan(tmp_path, "pkg.server.create_server"))
    other = tmp_path / "other"
    other.mkdir()
    out = lint(serve_plan(other, "pkg.server.create_server(lambda: 1)"))
    assert f"PROBE: serve=pkg.server.create_server(lambda: 1) arguments: Lambda; {TAIL}" in out
