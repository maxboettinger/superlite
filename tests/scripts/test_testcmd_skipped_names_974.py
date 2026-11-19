import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402
import testcmd  # noqa: E402

ROOT = SCRIPTS.parents[2]
HEAD = "=========================== short test summary info ============================"


def out(*lines, summary="1 passed, 4 skipped in 0.16s", before=()):
    return "\n".join([*before, ".ssss", HEAD, *lines, summary]) + "\n"


def names(text, rc=0):
    return testcmd.parse_output(text, rc)["skipped_names"]


def test_unfolded_lines_give_junit_ids():
    text = out("SKIPPED tests/a/test_x.py::test_s1 - Skipped: plain reason",
               "SKIPPED tests/a/test_x.py::TestC::test_m - Skipped",
               "SKIPPED tests/a/test_x.py::test_p[a::b] - Skipped: a - b",
               "SKIPPED tests/a/test_x.py::test_bare")
    assert names(text) == ["tests/a/test_x.py::test_s1", "tests/a/test_x.py::test_m",
                           "tests/a/test_x.py::test_p[a::b]", "tests/a/test_x.py::test_bare"]


def test_module_level_skip_gets_the_junit_module_name():
    assert names(out("SKIPPED tests/e2e/test_mod.py - Skipped: whole module")) == ["tests/e2e/test_mod.py::tests.e2e.test_mod"]


def test_folded_lines_name_nothing():
    text = out("SKIPPED [2] tests/a/test_x.py:6: param skip", "SKIPPED [1] tests/a/test_x.py:3: plain reason")
    assert names(text) == []
    assert testcmd.parse_output(text, 0)["skipped"] == 4


def test_skips_named_on_a_red_run_too():
    text = out("FAILED tests/a/test_y.py::test_f - assert 1 == 2", "SKIPPED tests/a/test_x.py::test_s1 - why",
               summary="1 failed, 1 skipped in 0.2s")
    r = testcmd.parse_output(text, 1)
    assert r["skipped_names"] == ["tests/a/test_x.py::test_s1"]
    assert r["names"] == ["tests/a/test_y.py::test_f"]


def test_skip_lines_outside_the_short_summary_are_ignored():
    text = out("SKIPPED tests/a/test_x.py::test_s1 - why", before=["SKIPPED tests/a/test_x.py::test_early - printed by a test"])
    assert names(text) == ["tests/a/test_x.py::test_s1"]


def test_no_short_summary_no_names():
    assert names("SKIPPED tests/a/test_x.py::test_s1 - why\n1 passed, 1 skipped in 0.1s\n") == []
    assert names("1 passed, 1 skipped in 0.1s\n") == []


def test_names_dedupe_and_cap_at_50():
    lines = [f"SKIPPED tests/a/test_x.py::test_{i} - r" for i in range(60)]
    lines.insert(1, "SKIPPED tests/a/test_x.py::TestC::test_0 - r")
    got = names(out(*lines, summary="61 skipped in 1.0s"))
    assert got == [f"tests/a/test_x.py::test_{i}" for i in range(50)]


def test_names_match_the_junit_ids(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "test_a.py").write_text(
        "import pytest\n"
        "def test_ok(): pass\n"
        "@pytest.mark.skip(reason='plain reason')\n"
        "def test_s1(): pass\n"
        "@pytest.mark.parametrize('x', [1, 'a::b'])\n"
        "def test_p(x): pytest.skip('param skip')\n"
        "class TestC:\n"
        "    def test_m(self): pytest.skip()\n")
    (tmp_path / "pkg" / "test_mod.py").write_text("import pytest\npytest.skip('whole module', allow_module_level=True)\n")
    xml = tmp_path / "junit.xml"
    r = subprocess.run([sys.executable, "-m", "pytest", "pkg", "-q", "-rs", "--no-fold-skipped", "-p", "no:cacheprovider",
                        "-p", "no:xdist", f"--rootdir={tmp_path}", "-o", "junit_family=xunit1", f"--junitxml={xml}"],
                       cwd=tmp_path, capture_output=True, text=True, timeout=120)
    parsed = testcmd.parse_output(r.stdout + r.stderr, r.returncode)
    counts, _failures, _files = run_tests.merge_junit([xml])
    assert parsed["skipped"] == 5 and len(parsed["skipped_names"]) == 5
    assert sorted(parsed["skipped_names"]) == sorted(counts["skipped_tests"])


def test_docs_name_the_repo_command():
    text = (ROOT / "docs" / "testing.md").read_text()
    assert "uv run --group dev python -m pytest tests -q -rfEs --no-fold-skipped -p no:cacheprovider -n 4" in text
    assert "`--no-fold-skipped` needs pytest 8.3 or newer." in text
