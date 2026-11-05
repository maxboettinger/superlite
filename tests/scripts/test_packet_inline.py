"""Tests for pt_review packet --inline (#130): a review packet for an inline build, from a spec instead of a plan."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"

SPEC = ("# Spec: double the value\n\n`a.py` doubles z. Ruling: keep the module flat.\n\n"
        "## Review Focus\n\n- a: numeric\n- FOCUS-LINE check the doubling\n")


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "T")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / ".gitignore").write_text("packet.md\nspec.md\nprev.md\n", encoding="utf-8")
    (tmp_path / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "a" / "core.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "a" / "core.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    return tmp_path


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "packet", "--root", str(repo), "--out", str(repo / "packet.md"),
                           "--wait-timeout", "1", *args], capture_output=True, text=True, timeout=60)


def inline(repo: Path, *extra: str) -> str:
    base = git(repo, "rev-parse", "HEAD")
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base, *extra)
    assert r.returncode == 0, r.stderr
    return (repo / "packet.md").read_text(encoding="utf-8")


def section(text: str, title: str) -> str:
    start = text.index(title)
    nxt = text.find("\n## ", start + len(title))
    return text[start: nxt if nxt != -1 else len(text)]


def test_inline_never_takes_the_fast_path(repo):
    s = inline(repo)
    assert s.startswith("# Review packet: REVIEW REQUIRED (inline build)")
    assert "FAST PATH" not in s and "Reply with a short APPROVED" not in s


def test_inline_spec_section_holds_the_spec_without_its_focus(repo):
    spec = section(inline(repo), "## 0. Spec")
    assert "Ruling: keep the module flat." in spec
    assert "FOCUS-LINE" not in spec


def test_inline_review_focus_comes_from_the_spec(repo):
    assert "FOCUS-LINE check the doubling" in section(inline(repo), "## 7. Review Focus")


def test_inline_skips_probe_coverage_items(repo):
    s = inline(repo)
    assert "no `verified` entry for category" not in s


def test_inline_marks_the_contract_check_not_run(repo):
    assert "## 3. Contract check: not run (inline build)" in inline(repo)


def test_inline_lists_untracked_files_in_the_stat(repo):
    (repo / "a" / "new.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    stat = section(inline(repo), "## 6. Diff stat")
    assert re.search(r"^ a/new\.py +\| 2 \+\+$", stat, re.M)
    assert "2 files changed" in stat


def test_inline_shows_untracked_files_as_added_hunks(repo):
    (repo / "a" / "new.py").write_text("x = 1\nNEW-LINE = 2\n", encoding="utf-8")
    ex = section(inline(repo), "## 8. Source excerpts")
    assert "### a/new.py" in ex and "+NEW-LINE = 2" in ex


def test_inline_leaves_out_untracked_superlite_files(repo):
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "notes.md").write_text("scratch\n", encoding="utf-8")
    assert ".superlite/notes.md" not in inline(repo)


def test_regular_packet_still_leaves_out_untracked_files(repo):
    (repo / "plan.md").write_text("# p\n\n## Review Focus\n- none\n", encoding="utf-8")
    (repo / "a" / "new.py").write_text("x = 1\n", encoding="utf-8")
    r = run(repo, "--plan", str(repo / "plan.md"), "--base", git(repo, "rev-parse", "HEAD"))
    assert r.returncode == 0, r.stderr
    assert "a/new.py" not in (repo / "packet.md").read_text(encoding="utf-8")


def test_previous_rounds_get_their_own_section(repo):
    (repo / "prev.md").write_text("Round 1: a/core.py:2 - off by one - fixed in abc123\n", encoding="utf-8")
    prev = section(inline(repo, "--previous", str(repo / "prev.md")), "## 0b. Earlier review rounds")
    assert "Round 1: a/core.py:2 - off by one - fixed in abc123" in prev


def test_previous_rounds_are_capped(repo):
    (repo / "prev.md").write_text("finding line\n" * 1000, encoding="utf-8")
    prev = section(inline(repo, "--previous", str(repo / "prev.md")), "## 0b. Earlier review rounds")
    assert len(prev) < 4200 and "(truncated)" in prev


def test_inline_needs_a_spec(repo):
    r = run(repo, "--inline")
    assert r.returncode == 2 and "--inline needs --spec" in r.stderr


def test_inline_rejects_a_plan(repo):
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--plan", str(repo / "spec.md"))
    assert r.returncode == 2 and "--spec in place of --plan" in r.stderr


def test_spec_needs_inline(repo):
    r = run(repo, "--spec", str(repo / "spec.md"))
    assert r.returncode == 2 and "--spec needs --inline" in r.stderr


def test_packet_without_inline_needs_a_plan(repo):
    r = run(repo)
    assert r.returncode == 2 and "packet needs --plan" in r.stderr


def test_missing_spec_file_is_an_error(repo):
    r = run(repo, "--inline", "--spec", str(repo / "nope.md"))
    assert r.returncode == 2 and "spec not found" in r.stderr


def test_missing_previous_file_is_an_error(repo):
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--previous", str(repo / "nope.md"))
    assert r.returncode == 2 and "previous rounds not found" in r.stderr


def test_final_reviewer_fast_path_keys_on_the_header():
    agent = (HERE.parent.parent / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
    rule = next(ln for ln in agent.splitlines() if ln.startswith("- Fast path"))
    assert "`FAST PATH`" in rule and "inline" in rule


def stat_of(repo: Path) -> str:
    return section(inline(repo), "## 6. Diff stat")


def test_inline_leaves_out_untracked_input_files_given_from_another_cwd(repo):
    notes = repo / "notes"
    notes.mkdir()
    (notes / "spec.md").write_text(SPEC, encoding="utf-8")
    (notes / "prev.md").write_text("Round 1: none\n", encoding="utf-8")
    rel = Path(repo.name) / "notes"
    r = subprocess.run([sys.executable, str(SCRIPT), "packet", "--root", str(repo), "--inline",
                        "--spec", str(rel / "spec.md"), "--previous", str(rel / "prev.md"), "--out", str(rel / "out.md"),
                        "--base", git(repo, "rev-parse", "HEAD"), "--wait-timeout", "1"],
                       capture_output=True, text=True, timeout=60, cwd=repo.parent)
    assert r.returncode == 0, r.stderr
    assert "notes/" not in section((notes / "out.md").read_text(encoding="utf-8"), "## 6. Diff stat")


def test_inline_shows_a_binary_untracked_file_as_bin(repo):
    (repo / "a" / "blob.bin").write_bytes(b"\x00\x01\x02\x00")
    assert re.search(r"^ a/blob\.bin +\| Bin$", stat_of(repo), re.M)


def test_inline_counts_an_empty_untracked_file(repo):
    (repo / "a" / "empty.py").write_text("", encoding="utf-8")
    assert re.search(r"^ a/empty\.py +\| 0$", stat_of(repo), re.M)


def test_inline_leaves_out_an_untracked_nested_repo(repo):
    sub = repo / "sub"
    sub.mkdir()
    git(sub, "init", "-q")
    (sub / "x.py").write_text("x = 1\n", encoding="utf-8")
    assert "sub" not in stat_of(repo)


def test_inline_caps_the_untracked_files(repo):
    many = repo / "gen"
    many.mkdir()
    for n in range(203):
        (many / f"f{n:03}.py").write_text("x = 1\n", encoding="utf-8")
    s = inline(repo)
    assert "gen/f000.py" in s and "gen/f200.py" not in s
    assert "(+3 more untracked files not shown)" in section(s, "## 6. Diff stat")


def test_inline_lists_hidden_untracked_folders_last(repo):
    env = repo / ".venv"
    env.mkdir()
    for n in range(201):
        (env / f"m{n:03}.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "a" / "new.py").write_text("x = 1\n", encoding="utf-8")
    assert "### a/new.py" in section(inline(repo), "## 8. Source excerpts")


def test_spec_section_keeps_fenced_heading_lines(repo):
    (repo / "spec.md").write_text("# Spec\n\n```\n# not a heading\n```\n\n## Review Focus\n- x\n", encoding="utf-8")
    spec = section(inline(repo), "## 0. Spec")
    assert "\n# not a heading\n" in spec and "### Spec" in spec


def test_final_reviewer_lists_what_it_checked():
    agent = (HERE.parent.parent / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
    assert "`Checked:`" in agent and "8 words" in agent and "unverified" in agent
    assert "outside the 300-word cap" in agent
    assert "starting directly with:\n`Verdict:" in agent
