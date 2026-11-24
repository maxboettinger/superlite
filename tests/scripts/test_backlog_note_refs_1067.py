"""A standing note's outside paths are copied into the lead worktree's .superlite/briefs/ref/ and the note names the copies (#1067)."""
import os, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import findings  # noqa: E402
import fleet  # noqa: E402
import fleet_roles  # noqa: E402

B = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}
CTX = {"sl": "/x/sl", "backlog_md": "/x/backlog.md", "repo": "o/r", "approved": None, "titles": {"7": "Seven"}, "summaries": []}
GENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


@pytest.fixture
def w(tmp_path, monkeypatch):
    tmp = tmp_path.resolve(); home = tmp / "home"; home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(fleet_roles, "SKILLS", tmp / "plug" / "skills")
    wt = tmp / "wt"; (wt / ".superlite").mkdir(parents=True)
    other = home / "github" / "other"; (other / "docs").mkdir(parents=True)
    (other / "docs" / "spec.md").write_text("spec\n"); (other / "README.md").write_text("readme\n")
    return type("W", (), {"home": home, "wt": wt, "other": other, "ref": wt / ".superlite" / "briefs" / "ref", "tmp": tmp})


def test_file_is_copied_and_the_note_names_the_copy(w):
    note, lines = bb.note_refs(f"Read {w.other}/docs/spec.md first.", w.wt)
    copy = w.ref / "github" / "other" / "docs" / "spec.md"
    assert copy.read_text() == "spec\n" and note == f"Read {copy} first."
    assert lines == [bb.REF_COPIED.format(n=1, ref=w.ref), bb.REF_READ.format(items=f"{w.other}/docs/spec.md")]


def test_tilde_folder_is_copied_with_its_files(w):
    note, lines = bb.note_refs("Reference repo: ~/github/other (read-only).", w.wt)
    dest = w.ref / "github" / "other"
    assert (dest / "docs" / "spec.md").read_text() == "spec\n" and (dest / "README.md").read_text() == "readme\n"
    assert note == f"Reference repo: {dest} (read-only)." and lines == [bb.REF_COPIED.format(n=1, ref=w.ref), bb.REF_READ.format(items="~/github/other")]


def test_git_folder_copies_listed_files_only(w):
    def git(*a): subprocess.run(["git", "-C", str(w.other), *a], check=True, capture_output=True, env=GENV)
    git("init", "-q"); (w.other / ".gitignore").write_text("build/\n")
    (w.other / "build").mkdir(); (w.other / "build" / "big.bin").write_text("x")
    git("add", ".gitignore", "README.md"); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
    bb.note_refs(f"See {w.other}.", w.wt)
    dest = w.ref / "github" / "other"
    assert (dest / "README.md").is_file() and (dest / "docs" / "spec.md").is_file() and (dest / ".gitignore").is_file()
    assert not (dest / "build").exists() and not (dest / ".git").exists()


def test_walk_skips_generated_folders_and_symlinks(w):
    (w.other / "node_modules").mkdir(); (w.other / "node_modules" / "m.js").write_text("m")
    os.symlink(w.home, w.other / "link")
    bb.note_refs(f"See {w.other}.", w.wt)
    dest = w.ref / "github" / "other"
    assert (dest / "README.md").is_file() and not (dest / "node_modules").exists() and not (dest / "link").exists()


def test_path_outside_home_mirrors_its_absolute_path(w):
    f = w.tmp / "elsewhere" / "x.md"; f.parent.mkdir(); f.write_text("x")
    note, _ = bb.note_refs(f"Read [x](file://{f}).", w.wt)
    copy = w.ref / str(f).lstrip("/")
    assert copy.read_text() == "x" and note == f"Read [x](file://{copy})."


def test_missing_capped_and_enclosing_paths_are_named_not_copied(w, monkeypatch):
    monkeypatch.setattr(bb, "REF_CAP", (10, 5000))
    text = f"Write {w.other}/new.md; read {w.other}/docs/spec.md and {w.other}/README.md; all of {w.tmp}."
    note, lines = bb.note_refs(text, w.wt)
    assert note == f"Write {w.other}/new.md; read {w.ref}/github/other/docs/spec.md and {w.other}/README.md; all of {w.tmp}."
    items = f"{w.other}/README.md (over the copy cap); {w.tmp} (holds the worktree)"
    assert lines == [bb.REF_COPIED.format(n=1, ref=w.ref), bb.REF_SKIPPED.format(items=items),
                     bb.REF_READ.format(items=f"{w.other}/docs/spec.md; {w.other}/README.md")]
    assert not (w.ref / "github" / "other" / "README.md").exists()


def test_rewritten_note_passes_the_spawn_scan(w):
    text = f"Read ~/github/other/docs/spec.md, {w.other}/README.md and {w.other}/gone.md; code in {w.wt}/src."
    note, _ = bb.note_refs(text, w.wt)
    assert fleet.outside_paths(note, w.wt, w.wt / ".superlite") == [f"{w.other}/gone.md"]


def test_inside_paths_and_a_missing_worktree_leave_the_note_alone(w):
    text = f"Code in {w.wt}/src and docs/x.md."
    assert bb.note_refs(text, w.wt) == (text, [])
    out = f"Read {w.other}/README.md"
    assert bb.note_refs(out, w.tmp / "nowhere") == (out, []) and not (w.tmp / "nowhere").exists()


def test_rerun_overwrites_the_copy(w):
    bb.note_refs(f"Read {w.other}/docs/spec.md", w.wt)
    (w.other / "docs" / "spec.md").write_text("v2\n")
    bb.note_refs(f"Read {w.other}/docs/spec.md", w.wt)
    assert (w.ref / "github" / "other" / "docs" / "spec.md").read_text() == "v2\n"


def test_lead_brief_copies_and_standing_note_reads_the_copies(w):
    t = bb.lead_brief(B, {**CTX, "note": f"Reference: {w.other}/docs/spec.md", "worktree": str(w.wt)})
    rows = t.splitlines(); i = rows.index(bb.NOTE_HEAD)
    assert rows[i + 1] == f"    Reference: {w.ref}/github/other/docs/spec.md"
    assert rows[i + 2] == bb.REF_COPIED.format(n=1, ref=w.ref)
    (w.wt / ".superlite" / "briefs" / "lead.md").write_text(t)
    lines = findings.standing_note(w.wt / ".superlite")
    assert lines == [bb.NOTE_HEAD, f"    Reference: {w.ref}/github/other/docs/spec.md"]
    assert fleet.outside_paths("\n".join(lines), w.wt, w.wt / ".superlite") == []


def test_lead_brief_without_worktree_keeps_the_note(w):
    t = bb.lead_brief(B, {**CTX, "note": f"Reference: {w.other}/docs/spec.md"})
    assert f"    Reference: {w.other}/docs/spec.md" in t.splitlines() and not w.ref.exists()


def test_backlog_md_names_the_copy_rule():
    text = (SCRIPTS.parent / "backlog.md").read_text(encoding="utf-8")
    assert "copied into `.superlite/briefs/ref/`" in text and "`Standing note: not copied`" in text and "(#1067)" in text


def test_symlinked_file_and_empty_folder_tokens_have_a_real_copy(w):
    link = w.home / "spec-link.md"; os.symlink(w.other / "docs" / "spec.md", link)
    empty = w.home / "empty"; empty.mkdir()
    note, _ = bb.note_refs(f"Read {link} and {empty}.", w.wt)
    assert note == f"Read {w.ref}/spec-link.md and {w.ref}/empty."
    assert (w.ref / "spec-link.md").read_text() == "spec\n" and (w.ref / "empty").is_dir()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a chmod 000 folder")
def test_unreadable_subfolder_is_named_not_copied_partially(w):
    locked = w.other / "locked"; locked.mkdir(); (locked / "s.md").write_text("s")
    locked.chmod(0)
    try:
        note, lines = bb.note_refs(f"See {w.other}.", w.wt)
    finally:
        locked.chmod(0o755)
    assert note == f"See {w.other}." and not (w.ref / "github" / "other").exists()
    assert len(lines) == 1 and lines[0].startswith("Standing note: not copied") and f"{w.other} (unreadable:" in lines[0]


def test_walk_stops_once_the_file_cap_is_passed(w, monkeypatch):
    monkeypatch.setattr(bb, "REF_CAP", (10 ** 9, 3))
    for i in range(20):
        (w.other / f"d{i}").mkdir(); (w.other / f"d{i}" / "f.md").write_text("f")
    walked, real = [], os.walk
    def spy(*a, **k):
        for t in real(*a, **k):
            walked.append(t[0]); yield t
    monkeypatch.setattr(os, "walk", spy)
    note, lines = bb.note_refs(f"See {w.other}.", w.wt)
    assert len(walked) <= 6 and note == f"See {w.other}."
    assert lines == [bb.REF_SKIPPED.format(items=f"{w.other} (over the copy cap)"), bb.REF_READ.format(items=str(w.other))]


def _git_repo(d, *paths):
    def git(*a): subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, env=GENV)
    git("init", "-q"); git("add", *paths); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a chmod 000 folder")
def test_git_listed_files_in_an_unreadable_subfolder_are_named_not_copied_partially(w):
    locked = w.other / "locked"; locked.mkdir(); (locked / "s.md").write_text("s")
    _git_repo(w.other, "README.md", "locked/s.md")
    locked.chmod(0)
    try:
        note, lines = bb.note_refs(f"See {w.other}.", w.wt)
    finally:
        locked.chmod(0o755)
    assert note == f"See {w.other}." and not (w.ref / "github" / "other").exists()
    assert len(lines) == 1 and lines[0].startswith("Standing note: not copied") and f"{w.other} (unreadable:" in lines[0]


def test_git_listing_over_the_cap_stops_checking_files_early(w, monkeypatch):
    monkeypatch.setattr(bb, "REF_CAP", (10 ** 9, 3))
    names = [f"f{i}.md" for i in range(20)]
    for n in names: (w.other / n).write_text("f")
    _git_repo(w.other, *names)
    seen = []
    for fn in ("stat", "lstat"):
        def spy(p, *a, _real=getattr(os, fn), **k):
            if str(p).startswith(f"{w.other}/f"): seen.append(str(p))
            return _real(p, *a, **k)
        monkeypatch.setattr(os, fn, spy)
    note, lines = bb.note_refs(f"See {w.other}.", w.wt)
    assert len(seen) <= 5 and note == f"See {w.other}."
    assert lines == [bb.REF_SKIPPED.format(items=f"{w.other} (over the copy cap)"), bb.REF_READ.format(items=str(w.other))]
