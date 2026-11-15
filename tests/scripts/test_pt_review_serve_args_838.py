"""#838: pt_review reads serve= arguments with ast, never eval: literals, the serve module's names and calls of the project's own code."""
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

APP = '''\
import os
from types import SimpleNamespace

import models838 as models

LIMIT = 3
_PRIVATE = "p"
cfg = SimpleNamespace(name="cfg")
TRACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "called")


class Workbook:
    def __init__(self, rows=0):
        self.rows = rows


class Trace:
    def __init__(self):
        open(TRACE, "w").close()


def make(*args, port=0, **kw):
    return {"args": args, "port": port, "kw": kw}
'''

MODELS = '''\
class Store:
    def __init__(self, path=":memory:"):
        self.path = path


def default_path():
    return "d.db"
'''

SERVER_APP = '''\
from http.server import BaseHTTPRequestHandler, HTTPServer


class Store:
    def __init__(self, path):
        self.path = path


def make(store=None, port=0):
    return HTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
'''


@pytest.fixture()
def make_server(tmp_path, monkeypatch):
    (tmp_path / "app838.py").write_text(APP, encoding="utf-8")
    (tmp_path / "models838.py").write_text(MODELS, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    ns: dict = {}
    exec(pt_review._SERVE_SNIPPET, ns)  # our own snippet text, the code under test
    yield ns["_make_server"]
    for name in ("app838", "models838"):
        sys.modules.pop(name, None)


def test_snippet_has_no_dynamic_execution():
    for word in ("eval(", "exec(", "compile("):
        assert word not in pt_review._SERVE_SNIPPET


def test_no_arguments_calls_the_factory_with_port_0(make_server):
    for args in (None, ""):
        got, fn = make_server("app838.make", args)
        assert got == {"args": (), "port": 0, "kw": {}} and fn.__name__ == "make"


def test_literals_names_and_project_calls_are_read(make_server):
    got, _fn = make_server("app838.make",
                           "Workbook(rows=2), models.Store(models.default_path()), LIMIT, cfg.name, -1, 2.5, 'x', "
                           "None, True, [1, (2, 3)], {'a': {4}}, set(), port=7, extra=_PRIVATE")
    wb, store, *rest = got["args"]
    assert type(wb).__name__ == "Workbook" and wb.rows == 2
    assert type(store).__name__ == "Store" and store.path == "d.db"
    assert rest == [3, "cfg", -1, 2.5, "x", None, True, [1, (2, 3)], {"a": {4}}, set()]
    assert got["port"] == 7 and got["kw"] == {"extra": "p"}


def test_starred_arguments_are_read(make_server):
    got, _fn = make_server("app838.make", "*[1, 2], *(LIMIT,), **{'k': cfg.name}")
    assert got["args"] == (1, 2, 3) and got["kw"] == {"k": "cfg"} and got["port"] == 0


REFUSED = [
    "__import__('os').system('touch {mark}')",  # #838: a builtin reached by name
    "os.system('touch {mark}')",  # the module imports os: a stdlib callee
    "Workbook.__init__.__globals__['os'].system('touch {mark}')",  # dunder attribute
    "__builtins__",  # dunder name
    "Trace(), os.system('touch {mark}')",  # refused before Trace() runs
    "1), __import__('os').system('touch {mark}'",  # closes the argument list early
    "(lambda: os.system('touch {mark}'))()",  # lambda callee
    "[os.system('touch {mark}') for _ in (1,)]",  # comprehension
    "open('{mark}', 'w')",  # a builtin is no module name
    "SimpleNamespace(a=1)",  # a stdlib class is not the project's own code
    "LIMIT + 1",  # arithmetic on a name
    "cfg['name']",  # subscript
    "Workbook()(1)",  # callee is a call result
    "f'{{LIMIT}}'",  # f-string
    "nosuch",  # unknown name
    "Workbook(",  # does not parse
]


@pytest.mark.parametrize("args", REFUSED)
def test_refused_arguments_run_nothing_and_read_as_unparsable(make_server, tmp_path, args):
    mark = tmp_path / "mark"
    with pytest.raises(SyntaxError, match="serve arguments unparsable"):
        make_server("app838.make", args.format(mark=mark))
    assert not mark.exists() and not (tmp_path / "called").exists()


def test_server_handle_reports_a_refused_argument_and_runs_nothing(tmp_path):
    (tmp_path / "srv838.py").write_text(SERVER_APP, encoding="utf-8")
    mark = tmp_path / "mark"
    handle = pt_review.ServerHandle(tmp_path, "srv838.make", f"__import__('os').system('touch {mark}')", timeout=20)
    try:
        assert handle.info is None
        assert handle.error.startswith("SyntaxError: serve arguments unparsable"), handle.error
    finally:
        handle.close()
    assert not mark.exists()


def test_server_handle_starts_with_a_project_call_argument(tmp_path):
    (tmp_path / "srv838.py").write_text(SERVER_APP, encoding="utf-8")
    handle = pt_review.ServerHandle(tmp_path, "srv838.make", "Store('x.db')", timeout=20)
    try:
        assert handle.error is None and handle.info and handle.info["port"] > 0
    finally:
        handle.close()


def test_generated_adapter_refuses_the_same_argument(tmp_path):
    (tmp_path / "srv838.py").write_text(SERVER_APP, encoding="utf-8")
    mark = tmp_path / "mark"
    plan = tmp_path / "plan.md"
    plan.write_text(f"**Probe entry:** serve=srv838.make(__import__('os').system('touch {mark}'))\n", encoding="utf-8")
    out = tmp_path / "adapter.py"
    assert pt_review.main(["adapter", "--plan", str(plan), "--root", str(tmp_path), "--out", str(out)]) == 0
    spec = importlib.util.spec_from_file_location("probe_adapter_838", out)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    try:
        with pytest.raises(SyntaxError, match="serve arguments unparsable"):
            adapter.start_server()
    finally:
        adapter.close()
        sys.modules.pop("srv838", None)
    assert not mark.exists()
