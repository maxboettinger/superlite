"""pt_review noise batch: prose is not a symbol, the newest incident entry wins, checks run in the project's Python."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from _fixtures import FIXTURES

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

PLAN_HEAD = """# kit plan

```mermaid
flowchart LR
%% taskgraph
T1 --> T2
```

"""


@pytest.fixture
def project_python(monkeypatch):
    """Swappable fake of _pyrun.project_python (T1): fake by default, the real one when SUPERLITE_REAL=1.
    Returns expected(root): call it before the code under test; it returns the interpreter pt_review must use for root."""
    if os.environ.get("SUPERLITE_REAL") == "1":
        def expected(root):
            venv_python = Path(root) / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("")  # looked up by is_file(), never run
            return str(venv_python)
        return expected
    monkeypatch.setattr(pt_review.pyrun, "project_python", lambda root: f"/fake/python-for-{Path(root).name}")
    return lambda root: f"/fake/python-for-{Path(root).name}"


def swift_plan(tmp_path: Path, produces: str, owns: str = "Sources/Kit/Foo.swift") -> "pt_review.Plan":
    (tmp_path / "plan.md").write_text(
        PLAN_HEAD + f"### T1 kit · Complexity 3\n**Owns:** {owns}\n**Produces:** {produces}\n\n"
        "### T2 client · Complexity 3\n**Owns:** Sources/Kit/Client.swift\n**Consumes:** x (T1)\n"
        "**Produces:** none\n\n## Review Focus\n- kit: state\n", encoding="utf-8")
    return pt_review.parse_plan(tmp_path / "plan.md")


# ---- symbol_names

def test_backticked_symbols_only():
    names = pt_review.symbol_names
    assert names("`Theme.Symbol.libraryTag`") == ["Theme.Symbol.libraryTag"]
    assert names("`Foo.bar` and `Baz`") == ["Foo.bar", "Baz"]
    assert names("Foo.bar and `Baz`") == ["Baz"]
    assert names("`LibraryView: View`") == ["LibraryView"]
    assert names("`Strings.libraryMoreTags(_ n: Int) -> String`") == ["Strings.libraryMoreTags"]
    assert names("`Box<T> wraps a value`") == ["Box"]
    assert names("`.iOS(.v17)`") == []
    assert names("`Foo` and `Foo`") == ["Foo"]


def test_unquoted_leading_identifier_only():
    names = pt_review.symbol_names
    assert names("Strings.libraryMoreTags(_ n: Int) -> String") == ["Strings.libraryMoreTags"]
    assert names("LibraryView: View") == ["LibraryView"]
    assert names("Box<T>") == ["Box"]
    assert names("Foo -> Bar") == ["Foo"]
    assert names("Foo.bar") == ["Foo.bar"]


def test_prose_item_yields_nothing(tmp_path):
    prose = "Package.swift platforms [.iOS(.v17)], targets Kit, init order"
    assert pt_review.symbol_names(prose) == []
    assert pt_review.symbol_names(f"`{prose}`") == []
    assert pt_review.symbol_names("init order") == []
    assert pt_review.symbol_names("") == []
    for produces in (prose, f"`{prose}`"):
        plan = swift_plan(tmp_path, produces, owns="Package.swift, Sources/Kit/Foo.swift")
        msgs, checked = pt_review.check_interfaces(plan, tmp_path, ["T1"])
        assert [m.msg for m in msgs] == [], produces
        assert checked == 0


def test_file_name_is_not_a_symbol():
    names = pt_review.symbol_names
    assert names("`Package.swift`") == []
    assert names("Package.swift") == []
    assert names("`Theme.md`") == []
    assert names("`data.json`") == []
    assert names("`Foo` in `Foo.swift`") == ["Foo"]
    assert names("`Foo.swiftUI`") == ["Foo.swiftUI"]


def test_declaration_keywords_are_not_symbols():
    names = pt_review.symbol_names
    assert names("`struct Foo`") == ["Foo"]
    assert names("`public final class Foo: Bar`") == ["Foo"]
    assert names("`static func make(_ x: Int) -> Foo`") == ["make"]
    assert names("`enum Mode: String`") == ["Mode"]
    assert names("`static`") == ["static"]
    assert names("struct Foo") == ["Foo"]
    assert names("enum Mode: String") == ["Mode"]
    assert names("func make(x: Int)") == ["make"]
    assert names("static func make() -> Foo") == ["make"]
    assert names("class hierarchy") == []  # lowercase word after a keyword is prose
    assert names("type system") == []
    assert names("struct Foo and Bar") == []
    assert names("classify(x)") == ["classify"]  # a name that merely starts with a keyword


def test_keyword_led_symbol_checked_by_name(tmp_path):
    (tmp_path / "Sources" / "Kit").mkdir(parents=True)
    (tmp_path / "Sources" / "Kit" / "Foo.swift").write_text("struct Foo {}\n", encoding="utf-8")
    for produces in ("`struct Foo`", "struct Foo"):
        msgs, checked = pt_review.check_interfaces(swift_plan(tmp_path, produces), tmp_path, ["T1"])
        assert (msgs, checked) == ([], 1), produces
    for produces in ("`struct Missing`", "struct Missing"):
        msgs, checked = pt_review.check_interfaces(swift_plan(tmp_path, produces), tmp_path, ["T1"])
        assert checked == 1 and len(msgs) == 1 and "`Missing`" in msgs[0].msg, produces


def test_swift_init_is_declared_by_init_signature(tmp_path):
    (tmp_path / "Sources" / "Kit").mkdir(parents=True)
    swift = tmp_path / "Sources" / "Kit" / "Foo.swift"
    for body in ("struct Foo {\n    init(x: Int) {}\n}\n", "struct Foo {\n    init?(x: Int) { return nil }\n}\n",
                 "struct Foo {\n    public init!(x: Int) {}\n}\n", "class Foo {\n    required init<T>(x: T) {}\n}\n"):
        swift.write_text(body, encoding="utf-8")
        msgs, checked = pt_review.check_interfaces(swift_plan(tmp_path, "Foo.init(x: Int)"), tmp_path, ["T1"])
        assert (msgs, checked) == ([], 1), body
    for body in ("struct Foo {}\n", "struct Foo {\n    // init(x: Int) {}\n    func make() { self.init(x: 1) }\n}\n",
                 "struct Foo {\n    var initial = 0\n}\n"):  # no declaration: a comment, a call, a longer name
        swift.write_text(body, encoding="utf-8")
        msgs, checked = pt_review.check_interfaces(swift_plan(tmp_path, "Foo.init(x: Int)"), tmp_path, ["T1"])
        assert checked == 1 and len(msgs) == 1 and "`init`" in msgs[0].msg, body


def test_planned_items_one_per_name(tmp_path):
    plan = swift_plan(tmp_path, "`Foo.bar` and `Baz`")
    assert [(p.task, p.qual, p.args_src) for p in pt_review.planned_items(plan)] == \
        [("T1", "Foo.bar", None), ("T1", "Baz", None)]


def test_signature_item_still_checked(tmp_path):
    (tmp_path / "Sources" / "Kit").mkdir(parents=True)
    (tmp_path / "Sources" / "Kit" / "Foo.swift").write_text("struct Foo {}\n", encoding="utf-8")
    plan = swift_plan(tmp_path, "Foo.missing(x: Int) -> Int")
    msgs, checked = pt_review.check_interfaces(plan, tmp_path, ["T1"])
    assert checked == 1
    assert len(msgs) == 1 and "`missing`" in msgs[0].msg
    plan = swift_plan(tmp_path, "Foo.missing(_ x: Int) -> Int")  # not a Python signature: name-only branch
    msgs, _ = pt_review.check_interfaces(plan, tmp_path, ["T1"])
    assert len(msgs) == 1 and "`missing`" in msgs[0].msg


# ---- superseded and incident_items

def entry(resolution, kind="exception", file="a.py", line=3, context="boom", agent="T1"):
    return {"file": file, "line": line, "kind": kind, "resolution": resolution, "context": context, "agent": agent}


def test_fixed_after_open_is_resolved():
    pair = [entry("open"), entry("fixed")]
    assert pt_review.superseded(pair) == {("a.py", 3)}
    items = pt_review.incident_items(pair)
    assert not any("unresolved" in it.title for it in items)


def test_open_after_fixed_stays_open():
    pair = [entry("fixed"), entry("open")]
    assert pt_review.superseded(pair) == set()
    items = pt_review.incident_items(pair)
    assert len(items) == 1 and "unresolved" in items[0].title


def test_identical_open_entry_after_fix_stays_open():
    log = [entry("open"), entry("fixed"), entry("open")]  # the last entry equals the first: dedupe must not hide it
    assert pt_review.superseded(log) == set()
    items = pt_review.incident_items(log)
    assert len(items) == 1 and "unresolved" in items[0].title


def test_regression_after_fix_is_logged_again(tmp_path, capsys):
    p = tmp_path / "noiseproj"
    shutil.copytree(FIXTURES / "review_noise", p)
    (p / "Sources/Kit/ThemeSymbol.swift").write_text("extension Mode {\n}\n")
    argv = ["contract", "--plan", str(p / "plan.md"), "--root", str(p), "--seam", "T1,T2"]
    log_path = p / ".superlite" / "incidents.jsonl"
    assert pt_review.main(argv) == 1
    first = json.loads(log_path.read_text().splitlines()[0])
    with open(log_path, "a", encoding="utf-8") as fh:  # the reviewer fixes it: newest entry at the location is resolved
        fh.write(json.dumps(dict(first, resolution="fixed", agent="reviewer")) + "\n")
    assert pt_review.main(argv) == 1  # the same mismatch is back: it must not be hidden by the superseded open entry
    capsys.readouterr()
    log = [json.loads(ln) for ln in log_path.read_text().splitlines()]
    assert [e["resolution"] for e in log] == ["open", "fixed", "open"]
    assert pt_review.superseded(log) == set()
    assert "unresolved" in pt_review.incident_items(log)[0].title
    assert pt_review.main(argv) == 1  # still open: a second run adds nothing
    capsys.readouterr()
    assert len(log_path.read_text().splitlines()) == 3


def test_verified_entries_ignored_by_superseded():
    assert pt_review.superseded([entry("open"), entry("fixed", kind="verified")]) == set()
    assert pt_review.superseded([entry("fixed"), entry("", kind="verified")]) == {("a.py", 3)}
    assert pt_review.superseded([entry("fixed", kind="verified")]) == set()


def test_superseded_resolution_case_and_locations():
    log = [entry("open"), entry("FIXED"), entry("open", line=9), entry("Wontfix", file="b.py", line=1)]
    assert pt_review.superseded(log) == {("a.py", 3), ("b.py", 1)}
    assert pt_review.superseded([]) == set()


def test_single_entries_unchanged():
    assert "unresolved" in pt_review.incident_items([entry("open")])[0].title
    assert pt_review.incident_items([entry("fixed")]) == []
    low = dict(entry("fixed"), confidence="low")
    assert "low confidence" in pt_review.incident_items([low])[0].title


# ---- test-failure incidents: the test name comes from the node id, not from the file name

def failure(context, file="tests/test_a.py"):
    return {"kind": "test-failure", "file": file, "context": context}


def test_failure_test_prefers_node_id_name():
    ft = pt_review._failure_test
    assert ft(failure("tests/test_a.py::test_x failed")) == ("tests/test_a.py", "test_x")
    assert ft(failure("tests/test_a.py::TestK::test_x failed")) == ("tests/test_a.py", "TestK::test_x")
    assert ft(failure("tests/test_a.py::test_x[1-2]: boom")) == ("tests/test_a.py", "test_x")
    assert ft(failure("test_x: AssertionError")) == ("tests/test_a.py", "test_x")
    assert ft(failure("tests/test_a.py failed")) == ("tests/test_a.py", "")  # only a path: file-level check
    assert ft(failure("see tests/test_a.py then test_y fails")) == ("tests/test_a.py", "test_y")
    assert ft(failure("next_tasks fails; shared state")) == ("tests/test_a.py", "")


def test_node_id_failure_stale_only_when_that_test_is_green():
    e = failure("tests/test_a.py::test_x failed")
    red = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::test_x: AssertionError"]}
    assert pt_review.stale_test_failure(e, red) is False  # the named test still fails: not hidden
    green = {"files": {"tests/test_a.py": [3, 0]}, "failures": []}
    assert pt_review.stale_test_failure(e, green) is True
    other = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::test_y: boom"]}
    assert pt_review.stale_test_failure(e, other) is True
    longer = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::test_x2: boom"]}
    assert pt_review.stale_test_failure(e, longer) is True  # test_x2 is another test
    in_class = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::TestK::test_x: boom"]}
    assert pt_review.stale_test_failure(failure("tests/test_a.py::TestK::test_x failed"), in_class) is False
    assert pt_review.stale_test_failure(failure("tests/test_a.py::TestK::test_x failed"), green) is True


# ---- project interpreter

class _Proc:
    def __init__(self, argv, **kw):
        _Proc.argv = list(argv)
        self.pid = 0

    def poll(self):
        return 0

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 0


def test_read_real_uses_project_python(tmp_path, monkeypatch, project_python):
    seen = []

    def fake_run(argv, **kw):
        seen.append(list(argv))
        return SimpleNamespace(stdout="@@SIG@@" + json.dumps([{"ok": True}]), stderr="")

    monkeypatch.setattr(pt_review.subprocess, "run", fake_run)
    want = project_python(tmp_path)
    pt_review.read_real(tmp_path, [("kit.mod", ["f"])])
    assert len(seen) == 1
    assert seen[0][0] == want
    assert seen[0][0] != sys.executable


def test_server_probe_uses_project_python(tmp_path, monkeypatch, project_python):
    monkeypatch.setattr(pt_review.subprocess, "Popen", _Proc)
    want = project_python(tmp_path)
    handle = pt_review.ServerHandle(tmp_path, "app:make", None, timeout=0.2)
    try:
        assert _Proc.argv[0] == want
        assert _Proc.argv[0] != sys.executable
    finally:
        handle.close()
