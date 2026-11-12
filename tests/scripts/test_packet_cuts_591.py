"""#591: the packet never cuts the diff stat or Review Focus, names every cut in its head and on stdout, and ends with a line count."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from test_packet_inline import SCRIPT, git, inline, repo, run, section  # noqa: F401  (repo is a fixture)

sys.path.insert(0, str(SCRIPT.parent))
import pt_review  # noqa: E402

TOOL_LINE = ("Answer in one turn: a verdict, then findings as `file:line - problem - fix`. Read the whole packet first; "
             "beyond it, Read only a file a `read <path> in full` marker or the Cut line names, the Render evidence images "
             "and what your brief names. Anything marked unverified is judged from its excerpt or listed as a finding.")
END_HEAD = ("This packet has {n} lines and ends with `End of packet ({n} lines)`; when one Read stops early, Read on with an offset. "
            "An APPROVED that leaves lines unread is `Verdict: APPROVED (partial: lines A-B not read)`.")


def plan_of(tmp_path: Path, body: str):
    p = tmp_path / "spec.md"
    p.write_text(body, encoding="utf-8")
    return pt_review.parse_plan(p), p


def test_spec_section_values(tmp_path):
    plan, p = plan_of(tmp_path, "# Spec\n\n" + "x" * 2000 + "\n")
    assert pt_review.spec_section(plan, Path("/r/spec.md")) == (pt_review.spec_text(plan), [])
    rul = "".join(f"- Ruling: r{i} " + "y" * 70 + "\n" for i in range(1, 101))
    plan, p = plan_of(tmp_path, "# Spec\n\n" + "b" * 1000 + "\n\n" + rul + "\n## Reviewer notes\n\nPREAMBLE-LINE\n")
    text, notes = pt_review.spec_section(plan, Path("/r/spec.md"), 6000)
    assert len(text) <= 6000 and "b" * 1000 in text and "- Ruling: r1 " in text and "PREAMBLE-LINE" in text
    assert "- Ruling: r100 " not in text
    m = re.search(r"\(truncated: (\d+) of 100 ruling lines cut at the spec cap; read /r/spec.md in full\)", text)
    assert m and 1 <= int(m.group(1)) <= 100
    assert text.index(m.group(0)) < text.index("PREAMBLE-LINE")
    assert notes == [f"section 0: {m.group(1)} of 100 ruling lines cut (read /r/spec.md in full)"]
    plan, p = plan_of(tmp_path, "# Spec\n\n" + "z" * 20000 + "\n")
    total = len(pt_review.spec_text(plan))
    text, notes = pt_review.spec_section(plan, Path("/r/spec.md"), 6000)
    assert len(text) <= 6000 and text.endswith(f"(truncated: spec cut at 6000 of {total} characters; read /r/spec.md in full)")
    assert notes == [f"section 0: spec cut at 6000 of {total} characters (read /r/spec.md in full)"]


def test_rulings_cut_before_spec_text(repo):
    rul = "".join(f"- Ruling: r{i} " + "y" * 70 + "\n" for i in range(1, 101))
    (repo / "spec.md").write_text("# Spec\n\n" + "b" * 1000 + "\n\n" + rul + "\n## Reviewer notes\n\nPREAMBLE-LINE\n\n"
                                 "## Review Focus\n\n- a: numeric\n", encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base)
    s0 = section((repo / "packet.md").read_text(encoding="utf-8"), "## 0. Spec")
    assert "PREAMBLE-LINE" in s0 and "ruling lines cut at the spec cap" in s0
    assert "cut: section 0: " in r.stdout and f" ruling lines cut (read {repo / 'spec.md'} in full)" in r.stdout


def test_head_tool_line_matches_reviewer(repo):
    s = inline(repo)
    assert s.splitlines()[2] == TOOL_LINE
    assert "no tools" not in s


def test_end_of_packet_line_counts_lines(repo):
    s = inline(repo)
    lines = s.splitlines()
    n = len(lines)
    assert lines[-1] == f"End of packet ({n} lines)"
    assert END_HEAD.format(n=n) in lines


def test_focus_and_stat_never_cut(repo):
    items = "".join(f"- RF-ITEM-{i} " + "f" * 108 + "\n" for i in range(1, 41))
    (repo / "spec.md").write_text("# Spec\n\n`a.py` doubles z.\n\n## Review Focus\n\n" + items, encoding="utf-8")
    d = repo / "many"
    d.mkdir()
    for i in range(300):
        (d / f"f{i:03d}.txt").write_text("1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "many")
    for i in range(300):
        (d / f"f{i:03d}.txt").write_text("2\n", encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base, "--max-tokens", "2000")
    assert r.returncode == 0, r.stderr
    s = (repo / "packet.md").read_text(encoding="utf-8")
    assert "- RF-ITEM-40 " in section(s, "## 7. Review Focus")
    assert "many/f299.txt" in section(s, "## 6. Diff stat")
    assert "packet over the size cap by " in r.stdout
    assert "(packet truncated at the size cap)" not in s


def test_over_cap_shrinks_section_8_only(repo):
    for i in range(8):
        (repo / "a" / f"m{i}.py").write_text("".join(f"v{j} = {j}\n" for j in range(5)), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "m")
    for i in range(8):
        (repo / "a" / f"m{i}.py").write_text("".join(f"v{j} = {j + 1}\n" for j in range(400)), encoding="utf-8")
    base = git(repo, "rev-parse", "HEAD")
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base, "--max-tokens", "3000")
    assert r.returncode == 0, r.stderr
    s = (repo / "packet.md").read_text(encoding="utf-8")
    assert "FOCUS-LINE" in section(s, "## 7. Review Focus") and "a/m7.py" in section(s, "## 6. Diff stat")
    assert "insertion" in section(s, "## 6. Diff stat")
    assert section(s, "## 8. Source excerpts").split("\n", 1)[1].startswith("Left out: ")
    assert "(packet truncated at the size cap)" not in s


def test_cut_notes_on_stdout_and_head(repo):
    (repo / "prev.md").write_text("p" * 9000, encoding="utf-8")
    prev = repo / "prev.md"
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", git(repo, "rev-parse", "HEAD"), "--previous", str(prev))
    s = (repo / "packet.md").read_text(encoding="utf-8")
    assert section(s, "## 0b. Earlier review rounds").rstrip().endswith(
        f"(truncated: earlier rounds cut at 4000 of 9000 characters; read {prev} in full)")
    note = f"section 0b: earlier rounds cut at 4000 of 9000 characters (read {prev} in full)"
    assert f"cut: {note}" in r.stdout.splitlines()
    assert any(ln.startswith("Cut to fit the size cap: ") and note in ln for ln in s.splitlines())


def test_left_out_files_named_in_head(repo):
    base = git(repo, "rev-parse", "HEAD")
    r0 = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base)
    assert "Cut to fit" not in (repo / "packet.md").read_text(encoding="utf-8") and "cut:" not in r0.stdout
    for i in range(8):
        (repo / "a" / f"f{i}.py").write_text("".join(f"v{j} = {j}\n" for j in range(300)), encoding="utf-8")
    r = run(repo, "--inline", "--spec", str(repo / "spec.md"), "--base", base, "--max-tokens", "2500")
    s = (repo / "packet.md").read_text(encoding="utf-8")
    left = next(ln for ln in section(s, "## 8. Source excerpts").splitlines() if ln.startswith("Left out: "))
    names = left[len("Left out: "):]
    head = next(ln for ln in s.splitlines() if ln.startswith("Cut to fit the size cap: "))
    assert f"section 8 left out: {names}" in head
    assert f"cut: section 8 left out: {names}" in r.stdout.splitlines()
