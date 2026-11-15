"""Review packet clips very long diff lines (#914)."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import pt_review  # noqa: E402

clip = pt_review.clip_diff_lines


def test_short_lines_unchanged():
    lines = ["+a", " b", "-c"]
    out = clip(lines)
    assert out == ["+a", " b", "-c"]
    assert all(a is b for a, b in zip(out, lines))


def test_pair_shows_the_changed_word():
    pre, post = "a" * 7000, "b" * 7997
    old, new = "-" + pre + "old" + post, "+" + pre + "new" + post
    assert len(old) == 15001
    a, b = clip([old, new])
    note = " [line of 15000 chars, changed at col 7001; read the file for the rest]"
    assert len(a) < 800 and len(b) < 800
    assert "old" in a and "new" in b and "new" not in a and "old" not in b
    assert a.endswith(note) and b.endswith(note)


def test_pair_of_different_lengths():
    a, b = clip(["-" + "x" * 500, "+" + "x" * 500 + "tail"])
    assert "changed at col 501" in a and "changed at col 501" in b
    assert "tail" in b


def test_lone_long_line_keeps_its_head():
    assert clip(["+" + "y" * 1000]) == ["+" + "y" * 399 + " [+601 chars; read the file for the rest]"]


def test_headers_never_clipped():
    h = "+++ b/" + "p" * 600
    d = "--- a/" + "p" * 600
    assert clip([d, h]) == [d, h]
    assert clip(["@@ " + "z" * 600]) == ["@@ " + "z" * 600]


def test_excerpts_use_clipped_lines(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                       check=True, capture_output=True, env=env)
    git("init", "-q")
    (tmp_path / "t.txt").write_text("| " + "a" * 7000 + " old " + "b" * 8000 + "\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True, env=env).stdout.strip()
    (tmp_path / "t.txt").write_text("| " + "a" * 7000 + " new " + "b" * 8000 + "\n", encoding="utf-8")
    sec = pt_review.source_excerpts(tmp_path, base, ["t.txt"])
    assert len(sec) < 2500 and "read the file for the rest" in sec
    need = pt_review.excerpt_need(pt_review.changed_diffs(tmp_path, base, ["t.txt"])[1])
    assert need < 2500
