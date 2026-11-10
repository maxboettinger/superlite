"""#415: a class with no signature of its own (an exception subclass) is checked by existence and base class."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

ERRORS = '''\
class ParseError(Exception):
    pass


class LookupFailed(KeyError):
    """No __init__ of its own."""


class CodedError(ValueError):
    def __init__(self, msg: str, code: int = 1) -> None:
        super().__init__(msg)
        self.code = code


class Store(dict):
    pass


class Plain:
    def __init__(self, path: str) -> None:
        self.path = path


def boom(n: int) -> None:
    raise ParseError(n)
'''


def project(root: Path) -> Path:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "errors.py").write_text(ERRORS, encoding="utf-8")
    return root


def check(root: Path, produces: str) -> tuple[list[str], int]:
    project(root)
    (root / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        f"### T1 errors · Complexity 3\n**Owns:** src/pkg/errors.py\n**Produces:** {produces}\n\n"
        "## Review Focus\n- errors: state\n", encoding="utf-8")
    out, n = pt_review.check_interfaces(pt_review.parse_plan(root / "plan.md"), root, None)
    return [m.msg for m in out], n


@pytest.mark.parametrize("args_src, names", [
    ("Exception", ["Exception"]),
    ("KeyError, Mixin", ["KeyError", "Mixin"]),
    ("path: str", None),
    ("x=1", None),
    ("*a", None),
    ("a, /", None),
    ("*, a", None),
    ("", None),
])
def test_base_names(args_src, names):
    assert pt_review._base_names(args_src) == names


def test_exception_class_without_init_matches_its_base(tmp_path):
    assert check(tmp_path, "pkg.errors.ParseError(Exception)") == ([], 1)


def test_indirect_base_matches(tmp_path):
    assert check(tmp_path, "pkg.errors.LookupFailed(LookupError)") == ([], 1)


def test_several_exception_classes_log_nothing(tmp_path):
    produces = "pkg.errors.ParseError(Exception) · pkg.errors.LookupFailed(KeyError) · pkg.errors.CodedError(ValueError)"
    assert check(tmp_path, produces) == ([], 3)


def test_wrong_base_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.errors.ParseError(ValueError)")
    assert msgs == ["T1 Produces: pkg.errors.ParseError: base class 'ValueError' not in its bases "
                    "(Exception, BaseException, object)"]


def test_no_signature_error_is_gone(tmp_path):
    msgs, _n = check(tmp_path, "pkg.errors.ParseError(Exception) · pkg.errors.Store(path: str)")
    assert not any("no signature found" in m for m in msgs)
    assert msgs == []


def test_missing_class_still_reported(tmp_path):
    msgs, _n = check(tmp_path, "pkg.errors.Missing(Exception)")
    assert msgs == ["T1 Produces: pkg.errors.Missing: AttributeError: Missing not found in pkg.errors"]


def test_constructor_signature_still_compared(tmp_path):
    msgs, _n = check(tmp_path, "pkg.errors.CodedError(msg: str, code: int = 2)")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'code' default is 1, planned 2")


def test_plain_class_constructor_unchanged(tmp_path):
    assert check(tmp_path, "pkg.errors.Plain(path: str) · pkg.errors.Plain(path)") == ([], 2)


def test_read_real_reports_bases(tmp_path):
    project(tmp_path)
    got = pt_review.read_real(tmp_path, [("pkg.errors", ["ParseError"]), ("pkg.errors", ["Plain"]),
                                         ("pkg.errors", ["boom"])])
    assert got[0]["ok"] is True
    assert got[0]["params"] is None
    assert got[0]["bases"] == ["Exception", "BaseException", "object"]
    assert got[0]["file"].endswith("errors.py")
    assert got[1]["bases"] == ["object"]
    assert [p["name"] for p in got[1]["params"]] == ["path"]
    assert got[2]["bases"] is None
