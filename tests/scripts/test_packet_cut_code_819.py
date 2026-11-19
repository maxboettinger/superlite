"""#819: a packet whose section 8 cut a changed code file's diff is never the fast path and names the files to read."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_packet_inline import SCRIPT, git

sys.path.insert(0, str(SCRIPT.parent))
import pt_review  # noqa: E402

PLAN = ("# p\n\n### T1 thing · Complexity 1\n**Owns:** src/big.py, docs/big.md, tests/test_big.py\n\n"
        "## Review Focus\n- none\n")
CUT = "Nothing is open, but section 8 cut the diff of changed code files: read each file the `Read in full` line above names, then review it; the fast path does not apply."


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "T")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / ".gitignore").write_text("packet.md\n.superlite/\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    for f in ("src/big.py", "docs/big.md", "tests/test_big.py"):
        (tmp_path / f).parent.mkdir(exist_ok=True)
        (tmp_path / f).write_text("# base\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def change(proj: Path, files: list[str], n: int) -> None:
    for f in files:
        (proj / f).write_text("".join(f"line_{i} = {i}\n" for i in range(n)), encoding="utf-8")


def packet(proj: Path, *extra: str) -> tuple[subprocess.CompletedProcess, str]:
    base = git(proj, "rev-parse", "HEAD")
    r = subprocess.run([sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"), "--root", str(proj),
                        "--out", str(proj / "packet.md"), "--base", base, "--wait-timeout", "1", *extra],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r, (proj / "packet.md").read_text(encoding="utf-8")


def test_cut_code_files_filters():
    text = ("Left out: a.py, docs/x.md\n(truncated: 5 of 90 diff lines shown, size cap; read b/c.py in full)\n"
            "(truncated: 5 of 9 diff lines shown, size cap; read tests/test_d.py in full)")
    assert pt_review.cut_code_files(text) == ["a.py", "b/c.py"]
    assert pt_review.cut_code_files("- none (no changed hunks in the hot-spot files)") == []


def test_fast_packet_with_cut_code_is_review_required(proj):
    change(proj, ["src/big.py"], 400)
    r, t = packet(proj, "--max-tokens", "1500")
    assert t.splitlines()[0] == "# Review packet: REVIEW REQUIRED (code diffs cut)"
    assert CUT in t.splitlines()
    ls = t.splitlines()
    assert next(k for k, x in enumerate(ls) if x.startswith("Read in full before your verdict")) < ls.index(CUT)
    assert "Reply with a short APPROVED" not in t
    assert r.stdout.splitlines()[0].endswith("- 0 open item(s), 1 cut code diff(s)")


def test_must_read_line_names_cut_code(proj):
    change(proj, ["src/big.py"], 400)
    _, t = packet(proj, "--max-tokens", "1500")
    lines = t.splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith("Cut to fit the size cap:"))
    assert lines[i + 1] == "Read in full before your verdict (section 8 cut their diff; one Read each): src/big.py"
    (proj / ".superlite" / "test-summary.json").write_text(json.dumps(
        {"passed": 2, "failed": 1, "skipped": 0, "seconds": 1.0, "mode": "full",
         "failures": ["tests/test_big.py::test_x: bad"], "skipped_tests": [], "files": {"tests/test_big.py": [2, 1]}}),
        encoding="utf-8")
    _, t = packet(proj, "--max-tokens", "1500")
    lines = t.splitlines()
    assert lines[0] == "# Review packet: REVIEW REQUIRED"
    i = next(k for k, x in enumerate(lines) if x.startswith("Cut to fit the size cap:"))
    assert lines[i + 1].startswith("Read in full before your verdict")


def test_uncut_packet_stays_fast(proj):
    change(proj, ["src/big.py"], 5)
    r, t = packet(proj)
    assert t.splitlines()[0] == "# Review packet: FAST PATH"
    assert "Read in full before your verdict" not in t
    assert r.stdout.splitlines()[0].endswith("- FAST PATH")


def test_cut_test_or_md_only_stays_fast(proj):
    change(proj, ["docs/big.md", "tests/test_big.py"], 400)
    _, t = packet(proj, "--max-tokens", "1500")
    assert t.splitlines()[0] == "# Review packet: FAST PATH"
