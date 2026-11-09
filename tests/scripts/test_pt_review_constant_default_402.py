"""#402: a Produces default that names a module constant matches by name, else is skipped when not a literal."""
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

CORE = '''\
import functools
import re


def id_re():
    return re.compile(r"T\\d+")


TID = id_re()
OTHER = re.compile("x")
PORT = 8080


def handover(text: str, tid=TID) -> list:
    return []


def kw(text: str, *, tid=TID) -> list:
    return []


def serve(port: int = 8080) -> None:
    return None


def wrap(fn):
    @functools.wraps(fn)
    def inner(*a, **k):
        return fn(*a, **k)
    return inner


@wrap
def wrapped(text: str, tid=TID) -> list:
    return []


class Box:
    def put(self, x: int, tid=TID) -> None:
        return None
'''


def project(root: Path) -> Path:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "core.py").write_text(CORE, encoding="utf-8")
    return root


def check(root: Path, produces: str) -> tuple[list[str], int]:
    project(root)
    (root / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        f"### T1 core · Complexity 3\n**Owns:** src/pkg/core.py\n**Produces:** {produces}\n\n"
        "## Review Focus\n- core: state\n", encoding="utf-8")
    out, n = pt_review.check_interfaces(pt_review.parse_plan(root / "plan.md"), root, None)
    return [m.msg for m in out], n


@pytest.mark.parametrize("planned, real_repr, real_src, same", [
    ("TID", "re.compile('T\\\\d+')", "TID", True),
    ("metrics.TID", "re.compile('x')", "TID", True),
    ("TID", "re.compile('x')", "metrics.TID", True),
    ("TID", "re.compile('x')", None, True),
    ("TID", "re.compile('x')", "id_re()", True),
    ("TID", "None", "None", True),
    ("TID", "re.compile('x')", "OTHER", False),
    ("Path('.')", "PosixPath('.')", "Path('.')", True),
    ("0", "8080", "8080", False),
    ("0", "0", "ZERO", True),
    ("None", "re.compile('x')", "TID", False),
])
def test_same_default(planned, real_repr, real_src, same):
    assert pt_review._same_default(planned, real_repr, real_src) is same


def test_same_default_two_arguments_unchanged():
    assert pt_review._same_default("0", "0") is True
    assert pt_review._same_default("0", "8080") is False


@pytest.mark.parametrize("expr, parts", [
    ("TID", ["TID"]),
    ("metrics.TID", ["metrics", "TID"]),
    ("a.b.C", ["a", "b", "C"]),
    ("id_re()", None),
    ("None", None),
    ("x[0]", None),
    ("", None),
    (None, None),
    ("(", None),
])
def test_dotted(expr, parts):
    assert pt_review._dotted(expr) == parts


def test_constant_built_by_call_matches_by_name(tmp_path):
    assert check(tmp_path, "pkg.core.handover(text: str, tid=TID) -> list") == ([], 1)


def test_dotted_planned_name_matches_last_component(tmp_path):
    assert check(tmp_path, "pkg.core.handover(text: str, tid=core.TID) -> list") == ([], 1)


def test_keyword_only_method_and_wrapped_defaults_match(tmp_path):
    produces = ("pkg.core.kw(text: str, *, tid=TID) -> list · pkg.core.Box.put(x: int, tid=TID) -> None"
                " · pkg.core.wrapped(text: str, tid=TID) -> list")
    assert check(tmp_path, produces) == ([], 3)


def test_other_constant_name_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.handover(text: str, tid=OTHER) -> list")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'tid' default is TID, planned OTHER")


def test_literal_default_still_compared(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.serve(port: int = 0) -> None")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'port' default is 8080, planned 0")


def test_planned_name_for_literal_source_is_skipped(tmp_path):
    assert check(tmp_path, "pkg.core.serve(port: int = PORT) -> None") == ([], 1)


def test_read_real_reports_default_source(tmp_path):
    project(tmp_path)
    got = pt_review.read_real(tmp_path, [("pkg.core", ["handover"]), ("pkg.core", ["Box", "put"]),
                                         ("pkg.core", ["serve"]), ("pkg.core", ["wrapped"])])
    assert [p["default_src"] for p in got[0]["params"]] == [None, "TID"]
    assert [p["default_src"] for p in got[1]["params"]] == [None, "TID"]
    assert got[2]["params"][0]["default_src"] == "8080"
    assert [p["default_src"] for p in got[3]["params"]] == [None, "TID"]


def test_two_lambdas_on_one_line_do_not_borrow_each_others_default(tmp_path):
    project(tmp_path)
    mod = tmp_path / "src" / "pkg" / "lam.py"
    mod.write_text("ONE = 1\nTID = object()\nfirst, second = (lambda x=ONE: x), (lambda x=TID: x)\n", encoding="utf-8")
    (tmp_path / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        "### T1 lam · Complexity 3\n**Owns:** src/pkg/lam.py\n**Produces:** pkg.lam.second(x=TID)\n\n"
        "## Review Focus\n- lam: state\n", encoding="utf-8")
    out, _n = pt_review.check_interfaces(pt_review.parse_plan(tmp_path / "plan.md"), tmp_path, None)
    assert [m.msg for m in out] == []
