"""Guard false blocks (#554): read-only git apply, argv tuple unpack, f-string targets."""
from test_block_coordinator_edits import bash, proj  # noqa: F401


def test_git_apply_check_reads_only(proj):
    pre = "D=/tmp/x; git diff HEAD --binary > $D/b.patch; "
    assert bash(proj, pre + "git apply --check -R $D/b.patch").returncode == 0
    assert bash(proj, "git apply x.patch").returncode == 2


def test_argv_tuple_unpack(proj):
    body = "import sys\np,img=sys.argv[1],sys.argv[2]\nopen(p,'w').write('x')\nEOF"
    cmd = 'S=/tmp/sc; python3 -I - "$S/copy/A.swift" "$S/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd).returncode == 0
    cmd2 = 'python3 -I - "src/A.swift" "/tmp/sc/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd2).returncode == 2


def test_fstring_with_unknown_piece_stays_blocked(proj):
    def code(target: str) -> str:
        return "python3 - <<'EOF'\nfrom pathlib import Path\nx='../../src/a'\n" + target + ".write_text(x)\nEOF"

    assert bash(proj, code('Path(f".superlite/plan-parts/{letter}.md")')).returncode == 2
    assert bash(proj, code('Path(f"src/{n}.py")')).returncode == 2
    assert bash(proj, code("Path(f'.superlite/plan-parts/{x}')")).returncode == 2


def test_pins_that_pass_today(proj):
    note = 'echo "Left undone: x" >> .superlite/notes.md; python3 - <<\'EOF\'\nimport json\nprint(json.load(open("docs/plans/a.json")))\nEOF'
    assert bash(proj, note).returncode == 0
    assert bash(proj, "python3 -I - <<EOF\nimport json\nprint(json.load(open('docs/plans/a.json')))\nEOF").returncode == 0


def test_fstring_glob_directly_below_superlite_root_blocks(proj):
    bad = "python3 - <<'EOF'\nimport sys\nfrom pathlib import Path\nx = sys.argv[1]\nPath(f\".superlite/{x}\").write_text('a')\nEOF"
    assert bash(proj, bad).returncode == 2


# --- #664: a git-ignored, unowned path passes as an rm target and as a write target ----------------------------
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_judge as gj  # noqa: E402

PLAN_664 = "# Plan\n\n### T1 a\n**Owns:** src/a.py, .build/owned/\n\n### T2 b\n**Owns:** lib/b.py\n"


def _git(p, *a):
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


@pytest.fixture
def G(tmp_path):
    p = (tmp_path / "proj").resolve()
    (p / "src").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "docs" / "plans").mkdir(parents=True)
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(PLAN_664)
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / ".gitignore").write_text(".build/\n*.log\ntmp/\n")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    _git(p, "add", "-A")
    _git(p, "commit", "-q", "-m", "init")
    (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan), "stable": []}))
    return p


def jg(G, cmd, cwd=None):
    return gj.judge(cmd, cwd=str(cwd or G), project=str(G), mode="active", sds=(str(G / ".superlite"),))


def _files(d, n):
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"f{i}").write_text("x")
    return d


def test_rm_ignored_folder_of_2100_files_passes(G):
    _files(G / ".build" / "dd", 2100)
    os.symlink(G / "src" / "a.py", G / ".build" / "dd" / "link")
    os.link(G / "src" / "a.py", G / ".build" / "dd" / "hard")
    for cmd in ("rm -rf .build/dd", "rm -r .build/dd/", "cd .build && rm -rf dd", "rmdir .build/dd"):
        assert jg(G, cmd) is None, cmd
    assert jg(G, "rm .build/dd/hard") is None  # one name of a hard-linked file
    assert jg(G, "unlink .build/dd/f1") is None
    _files(G / "tmp" / "x", 3)
    assert jg(G, "rm -rf tmp") is None


def test_rm_ignored_owned_path_blocks(G):
    _files(G / ".build" / "owned", 3)
    for cmd in ("rm -rf .build/owned", "rm -rf .build"):
        v = jg(G, cmd)
        assert v is not None and v.kind == "code" and v.why == "owned by task T1", cmd


def test_rm_untracked_not_ignored_folder_of_2100_files_blocks(G):
    _files(G / "untr", 2100)
    v = jg(G, "rm -rf untr")
    assert v is not None and v.kind == "code" and v.rel == "untr"
    assert v.why == "not git-ignored; more than 2000 entries"


def test_untracked_not_ignored_folder_reasons(G):
    os.symlink(G / "src" / "a.py", _files(G / "t1", 1) / "l")
    os.link(G / "src" / "a.py", _files(G / "t2", 1) / "h")
    v1, v2 = jg(G, "rm -r t1"), jg(G, "rm -r t2")
    assert v1.kind == "code" and v1.why.startswith("not git-ignored; symlink")
    assert v2.kind == "code" and v2.why.startswith("not git-ignored; hard link")
    assert jg(G, "rm -r src").why == "tracked by git"


def test_redirect_tee_cp_mv_into_ignored_folder_pass(G):
    (G / ".build").mkdir()
    (G / ".build" / "old.log").write_text("x")
    for cmd in ("echo hi > .build/x.log", "xcodebuild test > .build/new/b.log 2>&1", "echo hi | tee .build/t.log",
                "cp src/a.py .build/copy.py", "mv .build/old.log .build/older.log", "echo hi >> run.log",
                "cd .build && echo hi > here.txt"):
        assert jg(G, cmd) is None, cmd


def test_writes_keep_their_blocks(G):
    (G / ".build").mkdir()
    os.link(G / "src" / "a.py", G / ".build" / "hard.log")
    v = jg(G, "echo hi > .build/hard.log")  # a write through a hard link reaches src/a.py
    assert v is not None and v.kind == "code"
    v = jg(G, "echo hi > src/new.py")
    assert v is not None and v.rel == "src/new.py" and v.why == "not git-ignored"
    v = jg(G, "echo hi > src/a.py")
    assert v is not None and v.rel == "src/a.py" and v.why == "tracked by git"
    _files(G / ".build" / "owned", 1)
    v = jg(G, "cp src/a.py .build/owned/f0")
    assert v is not None and v.why == "owned by task T1"
    v = jg(G, "echo hi > .build/*.log")  # a glob target: not housekeeping
    assert v is not None


def test_ignored_folder_holding_a_worktree_blocks(G):
    _git(G, "worktree", "add", "-q", str(G / "tmp" / "wts" / "wt"))
    for cmd in ("rm -rf tmp", "rm -rf tmp/wts", "rm -rf tmp/wts/wt"):
        v = jg(G, cmd)
        assert v is not None and v.why == "holds the linked worktree tmp/wts/wt", cmd
    v = jg(G, "echo hi > tmp/wts/wt/src/a.py")  # tracked in that worktree
    assert v is not None and v.why == "tracked by git"
    assert jg(G, "echo hi > tmp/wts/wt/build.log") is None  # ignored in that worktree too


def test_ignored_folder_holding_the_state_folder_blocks(G):
    sd = _files(G / "tmp" / "state", 1)
    v = gj.judge("rm -rf tmp", cwd=str(G), project=str(G), mode="active", sds=(str(G / ".superlite"), str(sd)))
    assert v is not None and v.why == "holds the run's state folder"


def test_git_and_run_paths_keep_their_rules(G):
    _git(G, "init", "-q", str(G / ".build" / "repo"))
    v = jg(G, "rm -rf .build/repo/.git")
    assert v is not None and v.why == ".git, .superlite and run files keep their own rules"
    assert jg(G, "rm -rf .build/repo") is None  # a nested repository under an ignored folder is build output


def test_no_plan_no_housekeeping(G):
    _files(G / ".build" / "dd", 1)
    (G / ".superlite" / "stable.json").unlink()
    v = jg(G, "rm -rf .build/dd")
    assert v is not None and v.why == "no run plan to read Owns from"


def test_block_prints_why_after_the_refused_line(G, monkeypatch, capsys):
    _files(G / ".build" / "owned", 1)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf .build/owned"}, "cwd": str(G)})))
    rc = gj.main(["--mode", "active", "--project", str(G), "--sd", str(G / ".superlite")])
    lines = capsys.readouterr().err.splitlines()
    assert rc == 2
    k = lines.index(gj.REFUSED.format("rm -rf .build/owned"))
    assert lines[k + 1] == "Not housekeeping: owned by task T1"
    assert lines[-2:] == [f"Absolute target: {G}/.build/owned", "Blocked target: .build/owned"]


# --- #665: $HOME, quoted values with spaces, perl's exec @ARGV, git config in a grep pattern --------------------
import sys as _sys665  # noqa: E402
from pathlib import Path as _P665  # noqa: E402

import pytest as _pt665  # noqa: E402

_sys665.path.insert(0, str(_P665(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
from guard_judge import judge as _judge665  # noqa: E402


@_pt665.fixture
def H(tmp_path, monkeypatch):
    p = (tmp_path / "p").resolve()
    (p / "src").mkdir(parents=True)
    (p / "src" / "x.py").write_text("x = 1\n")
    (p / ".superlite").mkdir()
    home = (tmp_path / "home").resolve()
    (home / "Library").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    for name in ("S", "T", "DD", "NOPE_665"):
        monkeypatch.delenv(name, raising=False)
    return str(p)


def jh(cmd, P):
    return _judge665(cmd, P, P, "active")


def test_home_resolves_like_tilde(H):
    for cmd in ('cp /tmp/x "$HOME/Library/x/x.pdf"', "cp /tmp/x $HOME/Library/x/x.pdf", "cp /tmp/x ${HOME}/Library/x.pdf",
                'T="$HOME/Library/x"; cp /tmp/x "$T/x.pdf"',
                'DD="$HOME/Library/Developer/Xcode/DerivedData"; for d in a b; do rm -rf "$DD/$d"; done'):
        assert jh(cmd, H) is None, cmd


def test_home_inside_the_project_still_blocks(H, monkeypatch):
    v = jh(f'HOME={H}; echo hi > "$HOME/src/y.py"', H)  # an assigned HOME wins
    assert v is not None and v.rel == "src/y.py"
    monkeypatch.setenv("HOME", H)
    v = jh('cp /tmp/x "$HOME/src/x.py"', H)
    assert v is not None and v.rel == "src/x.py"


@_pt665.mark.parametrize("value", ["", "rel/home"])
def test_home_unset_or_relative_stays_unknown(H, monkeypatch, value):
    monkeypatch.setenv("HOME", value)
    v = jh("echo hi > $HOME/x.txt", H)
    assert v is not None and v.word == "$HOME/x.txt"


def test_quoted_value_with_spaces_resolves(H, tmp_path):
    out = str((tmp_path / "a b").resolve())
    for cmd in (f'T="{out}/c"; cp /tmp/x "$T/x.pdf"', f'T="{out}"; echo hi > "$T/x.log"',
                'S=/tmp/s; T="$HOME/Library/x/File Provider Storage"; cp "$S/x.pdf" "$T/x.pdf"'):
        assert jh(cmd, H) is None, cmd


def test_unquoted_value_with_spaces_stays_unknown(H, tmp_path):
    v = jh(f'T="{tmp_path}/a b"; cp /tmp/x $T/x.pdf', H)
    assert v is not None and v.word == "$T/x.pdf"
    v = jh(f'T="{tmp_path}/a b"; cp /tmp/x "$T"/$T/x.pdf', H)
    assert v is not None and v.rel == "?"


def test_targets_in_the_project_still_block(H):
    v = jh(f'T="{H}/src/a b"; echo hi > "$T.py"', H)
    assert v is not None and v.rel == "src/a b.py"
    v = jh('cp /tmp/x "$NOPE_665/x.py"', H)
    assert v is not None and v.word == "$NOPE_665/x.py"


def test_perl_alarm_exec_argv_is_judged_by_its_command(H):
    for cmd in ("perl -e 'alarm 30; exec @ARGV' xcrun simctl launch booted x", "perl -e 'alarm 30; exec @ARGV' echo hi",
                "perl -e 'alarm shift; exec @ARGV' 30 echo hi", "perl -E 'alarm 5;exec(@ARGV);' ls"):
        assert jh(cmd, H) is None, cmd
    v = jh("perl -e 'alarm 30; exec @ARGV' rm src/x.py", H)
    assert v is not None and v.rel == "src/x.py"
    v = jh("perl -e 'alarm 30; exec @ARGV' sh -c 'echo hi > src/x.py'", H)
    assert v is not None and v.rel == "src/x.py"
    v = jh("perl -e 'alarm 30; system @ARGV' echo hi", H)  # another program: as today
    assert v is not None and v.rel == "?"


def test_git_lfs_env_with_a_grep_pattern_passes(H):
    assert jh("git lfs env 2>&1 | grep -i -e A -e B -e 'git config filter'", H) is None
    assert jh('git lfs env | grep -e "git config filter"', H) is None


def test_unknown_git_target_names_its_token(H):
    v = jh("git config alias.lfs x; git lfs env", H)
    assert v is not None and v.rel == "?"
    assert v.word == "? (from git: lfs: no git command, read as an alias while the command names git config)"
    v = jh("perl -e 'alarm 30; system @ARGV' echo hi", H)
    assert v.word == "? (from perl)"


# --- only a tracked .gitignore makes a path housekeeping (F-T1-1) and every non-git writer is covered (F-T1-2) ---
def test_exclude_file_ignore_does_not_count(G):
    with open(G / ".git" / "info" / "exclude", "a") as f:
        f.write("gen/\n")
    _files(G / "gen", 2100)  # over the 2000-entry limit of the not-ignored rule
    v = jg(G, "echo hi > gen/new.py")
    assert v is not None and v.why == "not git-ignored"
    v = jg(G, "rm -r gen")
    assert v is not None and v.why.startswith("not git-ignored")


def test_untracked_gitignore_does_not_count(G):
    (G / "extra").mkdir()
    (G / "extra" / ".gitignore").write_text("*.dat\n")
    v = jg(G, "echo hi > extra/a.dat")
    assert v is not None and v.why == "not git-ignored"


def test_negated_pattern_does_not_count(G):
    (G / ".gitignore").write_text(".build/\n*.log\n!keep.log\ntmp/\n")
    _git(G, "add", ".gitignore")
    _git(G, "commit", "-q", "-m", "neg")
    assert jg(G, "echo hi > other.log") is None
    v = jg(G, "echo hi > keep.log")
    assert v is not None and v.why == "not git-ignored"


def test_every_non_git_writer_covers_ignored_paths(G):
    (G / ".build").mkdir()
    (G / ".build" / "x.log").write_text("a")
    assert jg(G, "sed -i '' s/a/b/ .build/x.log") is None
    assert jg(G, "python3 -c \"open('.build/y.log','w')\"") is None
    v = jg(G, "sed -i '' s/a/b/ src/a.py")
    assert v is not None and v.kind == "code"


# --- perl alarm unwrap, deadline, .claude settings, per-command HOME (F-T1-3 .. F-T1-6) ---
def test_perl_alarm_unwrap_keeps_sh_and_switch_readings(H):
    for cmd in ("perl -e 'alarm 30; exec @ARGV' 'echo hi > src/x.py'", "perl -e 'alarm 30; exec @ARGV' -- rm src/x.py"):
        v = jh(cmd, H)
        assert v is not None and v.rel == "src/x.py", cmd
    assert jh("perl -e 'alarm 30; exec @ARGV' -w rm src/x.py", H) is not None
    assert jh("perl -e 'alarm 30; exec @ARGV' -- echo hi", H) is None
    assert jh("perl -e 'alarm 30; exec @ARGV' 'echo hi'", H) is None


def test_housekeeping_past_deadline_runs_no_git(G, monkeypatch):
    ctx = gj._Ctx("rm -rf .build/dd", str(G), "active", (str(G / ".superlite"),))
    ctx.deadline = 0.0
    from types import SimpleNamespace
    v = SimpleNamespace(rel=".build/dd", abs=str(G / ".build" / "dd"), kind="code", why="")

    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    assert gj._housekeeping(v, ctx, True) == (False, "git could not tell")
    assert not calls


def test_claude_settings_keep_their_rules(G):
    (G / ".gitignore").write_text(".build/\n*.log\ntmp/\n.claude/\n")
    _git(G, "add", ".gitignore")
    _git(G, "commit", "-q", "-m", "claude")
    (G / ".claude").mkdir()
    (G / ".claude" / "settings.local.json").write_text("{}")
    v = jg(G, "echo '{}' > .claude/settings.local.json")
    assert v is not None and v.why == ".claude settings keep their own rules"
    v = jg(G, "rm -rf .claude")
    assert v is not None and v.why == ".claude settings keep their own rules"


def test_linked_worktree_under_claude_is_judged_from_its_root(G):
    (G / ".gitignore").write_text(".build/\n*.log\ntmp/\n.claude/\n")
    _git(G, "add", ".gitignore")
    _git(G, "commit", "-q", "-m", "claude")
    (G / ".claude" / "worktrees").mkdir(parents=True)
    _git(G, "worktree", "add", "-q", "-b", "wt", ".claude/worktrees/wt")
    _files(G / ".claude" / "worktrees" / "wt" / ".build" / "dd", 3)
    assert jg(G, "rm -rf .claude/worktrees/wt/.build/dd") is None
    v = jg(G, "echo x > .claude/worktrees/wt/.claude/settings.local.json")
    assert v is not None and v.why == ".claude settings keep their own rules"


def test_per_command_home_does_not_reach_a_nested_shell(H, monkeypatch, tmp_path):
    for cmd in ('HOME=$PWD bash -c \'echo hi > "$HOME/src/x.py"\'', "env HOME=src sh -c 'echo hi > $HOME/x.py'"):
        v = jh(cmd, H)
        assert v is not None and v.word.startswith("$HOME/"), cmd
    t = (tmp_path / "tmp").resolve()
    t.mkdir()
    monkeypatch.setenv("TMPDIR", str(t))
    assert jh('bash -c \'echo hi > "$TMPDIR/x.py"\'', H) is None
    v = jh('TMPDIR=src bash -c \'echo hi > "$TMPDIR/x.py"\'', H)
    assert v is not None and v.word.startswith("$TMPDIR/")


def test_env_split_string_skips_leading_assignments(H):  # F-T1-7
    v = jh("env -S 'X=1 rm -rf src'", H)
    assert v is not None and v.rel == "src"
    v = jh("env -S \"HOME=x sh -c 'echo hi > \\$HOME/a'\"", H)
    assert v is not None and v.word.startswith("$HOME/")


def test_bare_cd_and_tilde_loop_use_the_assigned_home(H):  # F-T1-8
    v = jh("HOME=src; cd; rm a.py", H)
    assert v is not None and v.rel in ("src/a.py", "?")
    v = jh("HOME=src cd; rm src/a.py", H)
    assert v is not None and v.rel == "src/a.py"
    v = jh("HOME=src; for d in ~; do echo hi > $d/x; done", H)
    assert v is not None


def test_find_exec_keeps_the_per_command_home(H):  # F-T1-9
    for cmd in ("HOME=$PWD find . -maxdepth 0 -exec sh -c 'rm -rf \"$HOME/src\"' \\;",
                "env HOME=$PWD find . -maxdepth 0 -exec sh -c 'rm -rf \"$HOME/src\"' \\;"):
        v = jh(cmd, H)
        assert v is not None and v.word.startswith("$HOME/"), cmd


def test_cp_r_into_existing_ignored_folder_checks_links_below(G):
    out = G / ".build" / "out"
    (out / "src").mkdir(parents=True)
    os.link(G / "src" / "a.py", out / "src" / "a.py")
    v = jg(G, "cp -r src .build/out")  # writes through the hard link into src/a.py
    assert v is not None and v.why == "hard link a.py", v
    (out / "src" / "a.py").unlink()
    (out / "src").rmdir()
    (out / "src").mkdir()
    os.symlink(G / "src", out / "src" / "lnk")
    v = jg(G, "cp -r src .build/out")  # a folder symlink into the project
    assert v is not None and v.why == "symlink lnk", v
    (out / "src" / "lnk").unlink()
    os.symlink("/tmp", out / "src" / "lnk")  # outside the project: fine
    assert jg(G, "cp -r src .build/out") is None
    assert jg(G, "cp -r src .build/fresh") is None


def test_relative_exclude_file_on_a_tracked_gitignore_elsewhere_does_not_count(G):  # F-T1-11
    (G / "tests" / "fixtures").mkdir(parents=True)
    (G / "tests" / "fixtures" / ".gitignore").write_text("*\n")
    _git(G, "add", "-f", "tests/fixtures/.gitignore")
    _git(G, "commit", "-q", "-m", "fixtures")
    _git(G, "config", "core.excludesFile", "tests/fixtures/.gitignore")
    _files(G / "untr", 2100)  # over the limit of the not-ignored rule
    v = jg(G, "echo x > src/new.py")
    assert v is not None and v.why == "not git-ignored", v
    v = jg(G, "rm -rf untr")
    assert v is not None and v.why.startswith("not git-ignored"), v
    assert jg(G, "echo x > tmp/new.log") is None  # the root .gitignore still counts
    assert jg(G, "echo x > tests/fixtures/new.txt") is None  # a folder holding that .gitignore
