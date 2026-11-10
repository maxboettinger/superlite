"""#432: a planned name default is a mismatch when the code's default is a literal or a call."""
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
import re

TID = re.compile("T")
LIMIT = 10


def none_default(text: str, tid=None) -> list:
    return []


def call_default(text: str, tid=re.compile("T")) -> list:
    return []


def name_default(text: str, tid=TID) -> list:
    return []


def neg_default(n: int = -1) -> int:
    return n


def kw_none(text: str, *, tid=None) -> list:
    return []


def expr_default(n: int = LIMIT + 1) -> int:
    return n


class Box:
    def put(self, x: int, tid=None) -> None:
        return None
'''


def check(root: Path, produces: str) -> tuple[list[str], int]:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "pkg" / "core.py").write_text(CORE, encoding="utf-8")
    (root / "plan.md").write_text(
        "# p\n\n```mermaid\nflowchart LR\n%% taskgraph\nT1\n```\n\n"
        f"### T1 core · Complexity 3\n**Owns:** src/pkg/core.py\n**Produces:** {produces}\n\n"
        "## Review Focus\n- core: state\n", encoding="utf-8")
    out, n = pt_review.check_interfaces(pt_review.parse_plan(root / "plan.md"), root, None)
    return [m.msg for m in out], n


@pytest.mark.parametrize("src, hit", [
    ("None", True), ("-1", True), ("'x'", True), ("(1, 2)", True), ("[]", True), ("{}", True),
    ("set()", True), ("re.compile('T')", True), ("id_re()", True),
    ("TID", False), ("a.b", False), ("LIMIT + 1", False), ("x[0]", False), ("lambda: 0", False),
    ("{[]}", False), ("", False), (None, False), ("(", False),
])
def test_literal_or_call(src, hit):
    assert pt_review._literal_or_call(src) is hit


@pytest.mark.parametrize("planned, real_repr, real_src, same", [
    ("TID", "None", "None", False),
    ("TID", "re.compile('T')", "re.compile('T')", False),
    ("TID", "re.compile('x')", "id_re()", False),
    ("metrics.TID", "8080", "8080", False),
    ("TID", "-1", "-1", False),
    ("TID", "'x'", "'x'", False),
    ("TID", "()", "()", False),
    ("TID", "re.compile('x')", "TID", True),
    ("TID", "re.compile('x')", "metrics.TID", True),
    ("TID", "re.compile('x')", "OTHER", False),
    ("TID", "11", "LIMIT + 1", True),
    ("TID", "re.compile('x')", "x[0]", True),
    ("TID", "re.compile('x')", None, True),
    ("TID", "re.compile('x')", "", True),
    ("Path('.')", "PosixPath('.')", "None", True),
    ("0", "8080", "8080", False),
    ("0", "0", "ZERO", True),
])
def test_same_default(planned, real_repr, real_src, same):
    assert pt_review._same_default(planned, real_repr, real_src) is same


def test_none_default_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.none_default(text: str, tid=TID) -> list")
    assert len(msgs) == 1
    assert msgs[0].endswith("pkg.core.none_default: parameter 'tid' default is None, planned TID")


def test_call_default_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.call_default(text: str, tid=TID) -> list")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'tid' default is re.compile('T'), planned TID")


def test_keyword_only_and_method_none_defaults_are_mismatches(tmp_path):
    msgs, n = check(tmp_path, "pkg.core.kw_none(text: str, *, tid=TID) -> list · pkg.core.Box.put(x: int, tid=TID) -> None")
    assert n == 2
    assert len(msgs) == 2
    assert all(m.endswith("parameter 'tid' default is None, planned TID") for m in msgs)


def test_negative_literal_default_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.neg_default(n: int = LIMIT) -> int")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'n' default is -1, planned LIMIT")


def test_dotted_planned_name_against_none_is_a_mismatch(tmp_path):
    msgs, _n = check(tmp_path, "pkg.core.none_default(text: str, tid=core.TID) -> list")
    assert len(msgs) == 1
    assert msgs[0].endswith("parameter 'tid' default is None, planned core.TID")


def test_name_default_still_matches_by_name(tmp_path):
    assert check(tmp_path, "pkg.core.name_default(text: str, tid=TID) -> list") == ([], 1)


def test_other_expression_is_skipped(tmp_path):
    assert check(tmp_path, "pkg.core.expr_default(n: int = LIMIT) -> int") == ([], 1)
