"""#693: `__file__` and path calls in the target of a Python script's write."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_tools  # noqa: E402

F = "/p/s/m.py"


def py(code, **kw):
    return guard_tools.targets(["python3", "-c", code], **kw)


FORMS = [
    ("Path(__file__).parent / 'o.json'", "/p/s/o.json", True),
    ("Path(__file__).parent.parent / 'src' / 'a.py'", "/p/src/a.py", True),
    ("Path(__file__).resolve().parent.joinpath('o.json')", "/p/s/o.json", True),
    ("Path(__file__).with_name('o.json')", "/p/s/o.json", True),
    ("os.path.join(os.path.dirname(__file__), 'o.json')", "/p/s/o.json", False),
    ("os.path.realpath(__file__)", "/p/s/m.py", False),
    ("os.path.dirname(os.path.abspath(__file__)) + '/o.json'", "/p/s/o.json", False),
    ("pathlib.Path(__file__).parent / 'o.json'", "/p/s/o.json", True),
]


@pytest.mark.parametrize("expr,want,is_path", FORMS)
def test_file_dunder_forms(expr, want, is_path):
    head = "import os, pathlib\nfrom pathlib import Path\n"
    assert py(head + f"open({expr}, 'w')", file=F) == [want]
    if is_path:
        assert py(head + f"({expr}).write_text('x')", file=F) == [want]


def test_path_calls_on_literals():
    head = "import os\nfrom pathlib import Path\n"
    assert py(head + "open(Path('/a/b/c.py').parent / 'o.txt', 'w')") == ["/a/b/o.txt"]
    assert py(head + "open(os.path.join(os.path.dirname('/a/b/c.py'), 'o.txt'), 'w')") == ["/a/b/o.txt"]
    assert py(head + "open(os.path.normpath('/a/b/../c'), 'w')") == ["/a/c"]
    assert py(head + "open(Path('s/m.py').parent / 'o', 'w')") == ["s/o"]


@pytest.mark.parametrize("expr,want,is_path", FORMS)
def test_file_unknown_without_file(expr, want, is_path):
    head = "import os, pathlib\nfrom pathlib import Path\n"
    assert py(head + f"open({expr}, 'w')") == ["?"]


def test_file_unknown_in_node_code():
    assert guard_tools.targets(["node", "-e", "require('fs').writeFileSync(__filename, 'x')"], file=F) == ["?"]
    assert guard_tools.targets(["node", "-e", "require('fs').writeFileSync(__filename, 'x')"]) == ["?"]


def test_file_dunder_reassigned():
    code = "import os\n__file__ = input()\nopen(os.path.realpath(__file__), 'w')"
    assert py(code, file=F) == ["?"]
