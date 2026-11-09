"""Tests for pt_review packet: changed test files that do not fit section 8 go to a second shard in full (#381)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_shard", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_shard"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n"
SPEC = "# Spec: a\n\n`a.py` grows.\n\n## Review Focus\n\n- a: numeric\n"


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def body(n: int) -> str:
    return "".join(f"x_{i} = {i}\n" for i in range(n))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "T")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / ".gitignore").write_text("packet.md\npacket-tests.md\nspec.md\nplan.md\n", encoding="utf-8")
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    (tmp_path / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("A = 0\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "src" / "a.py").write_text("A = 0\n" + "".join(f"B{i} = {i}\n" for i in range(10)), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def packet(repo: Path, n_test_lines: int, *extra: str, inline: bool = False) -> tuple[str, subprocess.CompletedProcess]:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "tests" / "test_a.py").write_text(body(n_test_lines), encoding="utf-8")
    if not inline:
        git(repo, "add", "tests/test_a.py")
    src = ["--inline", "--spec", str(repo / "spec.md")] if inline else ["--plan", str(repo / "plan.md")]
    r = subprocess.run([sys.executable, str(SCRIPT), "packet", *src, "--root", str(repo), "--out", str(repo / "packet.md"),
                        "--wait-timeout", "1", "--base", base, *extra], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return (repo / "packet.md").read_text(encoding="utf-8"), r


def test_cut_files_values():
    text = ("Left out: a.py, tests/b.py\n### x\n(truncated: 5 of 9 diff lines shown, size cap; read tests/c.py in full)")
    assert pt.cut_files(text) == {"a.py", "tests/b.py", "tests/c.py"}
    assert pt.cut_files("### x\n```diff\n+a\n```") == set()


def test_shard_path_values():
    assert pt.shard_path(Path("/r/.superlite/review-packet.md")) == Path("/r/.superlite/review-packet-tests.md")


def test_long_test_file_goes_to_shard(repo):
    text, r = packet(repo, 300)
    shard = repo / "packet-tests.md"
    assert shard.is_file()
    s = shard.read_text(encoding="utf-8")
    assert "+x_0 = 0" in s and "+x_299 = 299" in s and "(truncated:" not in s
    assert "### tests/test_a.py" not in text and "### src/a.py" in text
    head = text.split("## ")[0]
    line = next(ln for ln in head.splitlines() if ln.startswith("Tests shard: 1 changed test file(s)"))
    assert line.endswith(f"read {shard} in full)")
    assert r.stdout.splitlines()[1].startswith(f"wrote {shard}")


def test_small_change_has_no_shard_and_removes_old_one(repo):
    (repo / "packet-tests.md").write_text("old shard\n", encoding="utf-8")
    text, _ = packet(repo, 20)
    assert not (repo / "packet-tests.md").exists()
    assert "Tests shard:" not in text
    assert "### tests/test_a.py" in text.split("## 8. ")[1]


def test_shard_respects_max_tokens(repo):
    _, _ = packet(repo, 300, "--max-tokens", "2000")
    s = (repo / "packet-tests.md").read_text(encoding="utf-8")
    assert len(s) <= int(2000 * 1.9)
    assert "(truncated:" in s


def test_inline_packet_shards_too(repo):
    packet(repo, 300, inline=True)
    s = (repo / "packet-tests.md").read_text(encoding="utf-8")
    assert "+x_299 = 299" in s


def test_hot_test_file_stays_in_section_8(repo):
    import json
    (repo / ".superlite").mkdir(exist_ok=True)
    (repo / ".superlite" / "incidents.jsonl").write_text(json.dumps(
        {"kind": "exception", "file": "tests/test_a.py", "line": 1, "context": "boom", "resolution": "", "agent": "T1"})
        + "\n", encoding="utf-8")
    text, _ = packet(repo, 300)
    assert "### tests/test_a.py" in text.split("## 8. ")[1]
    assert "+x_299 = 299" in (repo / "packet-tests.md").read_text(encoding="utf-8")
