# tests/scripts/test_brief_check_794.py
import os, subprocess, sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import brief_check as bc  # noqa: E402
import fleet_report as fr  # noqa: E402

MISSING = "ROOT=/no/such/tree names a folder that does not exist"


def git(repo, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    r = subprocess.run(["git", "-c", "commit.gpgsign=false", *a], cwd=repo, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(repo, lines, msg):
    (repo / "a.txt").write_text("".join(l + "\n" for l in lines))
    git(repo, "add", "a.txt")
    git(repo, "commit", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    c1 = commit(repo, ["one", "two", "three"], "c1")
    c2 = commit(repo, ["one", "TWO", "three"], "c2")
    return repo, c1, c2


def brief(tmp_path, text, name="brief.md"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_missing_root_flagged(tmp_path):
    assert bc.problems(brief(tmp_path, "ROOT=/no/such/tree\n")) == [MISSING]
    assert bc.problems(brief(tmp_path, "Root: /no/such/tree\n")) == ["Root: /no/such/tree names a folder that does not exist"]
    assert bc.problems(brief(tmp_path, "ROOT=trees/T1\n")) == []


def test_existing_root_and_applying_recipe_pass(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    assert bc.problems(brief(tmp_path, f"ROOT={repo}\nRun `git show {c2} | git apply -R`\n")) == []


def test_stale_recipe_flagged(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    commit(repo, ["one", "zwei", "three"], "c3")
    text = f"ROOT={repo}\nRun `git show {c2} | git apply -R`\n"
    out = bc.problems(brief(tmp_path, text))
    assert len(out) == 1
    assert out[0].startswith(f"recipe `git show {c2} | git apply -R` does not apply in {repo}: ")
    assert out[0].endswith("(a later commit rewrote those lines: build the mutation by hand)")
    inside = repo / "brief.md"
    inside.write_text(f"`git show {c2} | git apply -R`\n")
    out = bc.problems(str(inside))
    assert len(out) == 1 and "does not apply in" in out[0]


def test_apply_r_with_a_sha(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    text = f"ROOT={repo}\n`git apply -R {c2}`\n"
    assert bc.problems(brief(tmp_path, text)) == [
        f"recipe `git apply -R {c2}` names a commit, not a patch file (`git show {c2} | git apply -R` applies it)"]
    commit(repo, ["one", "zwei", "three"], "c3")
    out = bc.problems(brief(tmp_path, f"ROOT={repo}\n`git apply -R {c2}`\n`git show {c2} | git apply -R`\n"))
    assert len(out) == 2 and "names a commit" in out[0] and "does not apply in" in out[1]
    patch = git(repo, "format-patch", "-1", c2, "-o", str(tmp_path / "p"))
    git(repo, "reset", "-q", "--hard", c2)
    assert bc.problems(brief(tmp_path, f"ROOT={repo}\n`git apply -R {patch}`\n")) == []


def test_writing_producer_skipped(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    text = f"ROOT={repo}\n`git diff --output=out.txt HEAD~1 | git apply -R`\n`git show {c2} | git apply -R; rm -rf x`\n"
    assert bc.problems(brief(tmp_path, text)) == []
    assert not (repo / "out.txt").exists() and not (tmp_path / "out.txt").exists()


def test_producer_option_allow_list(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    commit(repo, ["one", "zwei", "three"], "c3")
    for prod in (f"git show {c2} --ext-diff", f"git show --textconv {c2}", f"git show -c {c2}"):
        assert bc.problems(brief(tmp_path, f"ROOT={repo}\n`{prod} | git apply -R`\n")) == []
    out = bc.problems(brief(tmp_path, f"ROOT={repo}\n`git show --format= {c2} | git apply -R`\n"))
    assert len(out) == 1 and "does not apply in" in out[0]


def test_recipe_producer_runs_no_textconv_driver(tmp_path):
    repo, c1, c2 = make_repo(tmp_path)
    marker = tmp_path / "textconv-ran"
    (repo / ".gitattributes").write_text("*.txt diff=probe\n")
    git(repo, "config", "diff.probe.textconv", f"sh -c 'touch {marker}; cat \"$1\"' sh")
    assert bc.problems(brief(tmp_path, f"ROOT={repo}\n`git show {c2} | git apply -R`\n")) == []
    assert not marker.exists()


def test_unreadable_brief_no_problems(tmp_path):
    assert bc.problems(str(tmp_path / "nope.md")) == []
    assert bc.problems(str(tmp_path)) == []
    many = "".join(f"ROOT=/no/such/tree{i}\n" for i in range(7))
    assert len(bc.problems(brief(tmp_path, many))) == 5


def test_note_text():
    assert bc.note([]) == ""
    assert bc.note(["a", "b"]) == "Brief check (sl, before sending): a; b."


def test_brief_message_flags_and_appends(tmp_path, capsys):
    p = brief(tmp_path, "ROOT=/no/such/tree\n")
    base = f"Read {p} and do what it says. {fr.WORK}"
    out = fr.brief_message("implementer", p)
    assert out == base + f" Brief check (sl, before sending): {MISSING}."
    assert capsys.readouterr().err.strip() == f"brief check: {p}: {MISSING}"
    clean = brief(tmp_path, "nothing here\n", "clean.md")
    assert fr.brief_message("implementer", clean) == f"Read {clean} and do what it says. {fr.WORK}"
    assert capsys.readouterr().err == ""


def test_final_reviewer_not_checked(tmp_path, capsys):
    p = brief(tmp_path, "ROOT=/no/such/tree\n")
    assert fr.brief_message("final-reviewer", p) == f"Review the packet {p} as your instructions say. {fr.REVIEW}"
    assert capsys.readouterr().err == ""


def test_annotations_are_list_of_str():
    assert bc.problems.__annotations__["return"] in (list[str], "list[str]")
    assert bc.note.__annotations__["problems"] in (list[str], "list[str]")
