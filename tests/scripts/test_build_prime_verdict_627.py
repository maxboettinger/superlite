"""#627: the prime's `Verdict:` line for a Swift project."""
import json
import sys

from test_plan_tools import SCRIPTS
from test_slim_prime import make, slim

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

LINE = ("- Verdict: sl run_tests runs the project's test command (maxapp test); a build pool may run it on another Mac. "
        "A product build, simulator or device run stays on this machine and is no proof unless your task names it.")


def cfg(tmp_path, **d):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(d), encoding="utf-8")


def test_swift_prime_has_verdict_line(tmp_path):
    cfg(tmp_path, language="swift", test="maxapp test")
    p = make(tmp_path)
    for extra in ((), ("--prime", "full")):
        _, text = slim(tmp_path, p, "s.md", *extra)
        assert text.splitlines().count(LINE) == 1
        lines = text.splitlines()
        assert lines[[i for i, x in enumerate(lines) if x.startswith("- Run the verify command")][0] + 1] == LINE


def test_python_prime_has_none(tmp_path):
    cfg(tmp_path, language="python", test="pytest")
    _, text = slim(tmp_path, make(tmp_path))
    assert "Verdict:" not in text


def test_resolve_error_adds_nothing(tmp_path):
    p = make(tmp_path)
    (tmp_path / "sitecustomize.py").write_text("", encoding="utf-8")
    import build_prime
    real = testcmd.resolve
    testcmd.resolve = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    try:
        out = build_prime.build_slim(p).decode()
    finally:
        testcmd.resolve = real
    assert "Verdict:" not in out and "# superlite prime" in out
