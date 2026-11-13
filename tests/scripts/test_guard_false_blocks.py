"""Coordinator guard false blocks (#79) and the limits kept or fixed from #64."""
import pytest

from test_block_coordinator_edits import bash, proj, run  # noqa: F401

PY_SRC = "import sys\np = sys.argv[1]\nt = open(p, encoding=\"utf-8\").read()\nopen(p, \"w\", encoding=\"utf-8\").write(t)\nEOF"


def at(proj, cmd, cwd):
    return run(proj, "Bash", {"command": cmd}, cwd=str(cwd))


def worktree(proj, name="wt"):
    wt = proj / ".claude" / "worktrees" / name
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {proj}/.git/worktrees/{name}\n")
    return wt


def human_proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    return tmp_path


# Case 1a: a module-qualified pathlib.Path(...) target is a literal like Path(...).
@pytest.mark.parametrize("target,code", [("docs/plans/a.md", 0), ("src/a.py", 2)])
def test_pathlib_path_target_is_read(proj, target, code):
    heredoc = f"python3 - <<'EOF'\nimport pathlib\np=pathlib.Path(\"{target}\"); s=p.read_text()\np.write_text(s)\nEOF"
    assert bash(proj, heredoc).returncode == code
    inline = f"python3 -c \"import pathlib; pathlib.Path('{target}').write_text('x')\""
    assert bash(proj, inline).returncode == code


# Case 1b: a $( ) inside a double-quoted word is judged alone, not with the whole command's quoted words unreadable.
def test_substitution_in_double_quotes_judges_its_body_alone(proj):
    log = "echo \"- dispatched T2 at $(date +%H:%M:%S); waiting: T6\" >> .superlite/progress.md; "
    assert bash(proj, log + "sed -i '' -e 's/^## A/## 1/' -e 's/^## B/## 2/' docs/plans/a.spec.md").returncode == 0
    assert bash(proj, log + "sed -i '' -e 's/a/b/' src/a.py").returncode == 2
    assert bash(proj, "echo \"$(rm src/a.py)\"; sed -i '' -e 's/a/b/' docs/plans/a.md").returncode == 2


# Case 3b: relative targets are judged from the directory the shell is in, inside the project too.
def test_cd_into_state_folder_judges_relative_targets_from_there(proj):
    fixes = proj / ".superlite" / "fixes"
    note = f"cat > F-T5-1.md <<'EOF'\n# F-T5-1\nWhere: Packages/Kit/Sources/A.swift\nEOF"
    assert bash(proj, f"mkdir -p {fixes} && cd {fixes} && {note}").returncode == 0   # folder made by the chain
    fixes.mkdir()
    assert bash(proj, f"cd {fixes} && {note}").returncode == 0
    assert bash(proj, f"cd {fixes}; echo x > F-1.md").returncode == 0


def test_cd_base_applies_only_after_the_cd(proj):
    (proj / ".superlite" / "fixes").mkdir()
    sd = proj / ".superlite"
    assert bash(proj, f"echo x > a.py; cd {sd} && echo y > b.md").returncode == 2
    assert bash(proj, f"cd {sd}/missing; echo x > a.py").returncode == 2   # a failed cd moves nowhere
    (proj / "src").mkdir()
    assert bash(proj, f"cd {proj}/src && echo x > docs/plans/a.md").returncode == 2   # src/docs/plans/a.md


@pytest.mark.parametrize("cmd", [
    # a missing folder: only a pure && chain stops when the cd fails
    "cd /tmp/nope-79 && true; echo x > src/a.py",
    "cd PROJ/.superlite/nope && echo ok || echo x > src/a.py",
    "echo go; cd PROJ/.superlite/nope && true; echo x > src/a.py",
    "! cd PROJ/.superlite/nope && echo x > src/a.py",
    # a cd that may not run moves nothing for sure: later paths are judged from both directories
    "false && cd PROJ/.superlite; echo x > src/a.py",
    "if [ -d /nope ]; then cd PROJ/.superlite; fi; echo x > src/a.py",
    "while false; do cd PROJ/.superlite; done; echo x > src/a.py",
    "a && (cd PROJ/.superlite && b) && echo x > src/a.py",
    # interpreter writer targets after a later cd are judged from both directories
    "true; cd PROJ/src && python3 -c \"open('docs/plans/a.py','w').write('x')\"",
    "true && cd PROJ/src && python3 -c \"open('docs/plans/a.py','w').write('x')\"",
])
def test_uncertain_cd_never_lets_project_code_through(proj, cmd):
    (proj / "src").mkdir()
    assert bash(proj, cmd.replace("PROJ", str(proj))).returncode == 2, cmd


@pytest.mark.parametrize("cmd,cwd", [
    # a relative cd moves nothing for the commands before it or outside its subshell
    ("echo x > src/a.py; cd .superlite", None),
    ("(cd .superlite && ls); echo x > src/a.py", None),
    # patch and git apply after a later cd into the project
    ("true; cd PROJ/src; git apply /tmp/fix.diff", "/tmp"),
    ("true; cd PROJ/src; patch -p1 -i /tmp/x.diff", "/tmp"),
    # a body that changes directory is judged from the project root
    ("bash -c \"cd PROJ/src && echo x > a.py\"", "PROJ/.superlite"),
    ("eval \"cd PROJ/src\"; echo x > a.py", "PROJ/.superlite"),
    ("cd PROJ/.superlite && eval \"cd PROJ/src\" && echo x > a.py", None),
    # loops and functions run a write after the cd
    ("for i in 1 2; do echo x > a.py; cd PROJ/src; done", "/tmp"),
    ("f(){ echo x > a.py; }; cd PROJ/src; f", "PROJ/.superlite"),
    # a voided base still judges from the cwd
    ("echo x > docs/plans/a.md; cd /tmp", "PROJ/src"),
    ("pushd .; echo x > ../a.py", "PROJ/src/pkg"),
    # cd targets that are part quoted or carry an option void the base
    ("true; cd \"$CLAUDE_PROJECT_DIR\"/src; echo x > a.py", "/tmp"),
    ("true; cd -P PROJ/src; echo x > a.py", "/tmp"),
    # an unreadable quoted target never fails open (bash 3.2 rejects a negative substring length)
    ("cd \"$(cat <<'EOF'\n/x\nEOF\n)\"; echo x > src/a.py", None),
])
def test_cd_forms_that_keep_project_code_blocked(proj, cmd, cwd):
    (proj / "src" / "pkg").mkdir(parents=True)
    cmd = cmd.replace("PROJ", str(proj))
    r = at(proj, cmd, cwd.replace("PROJ", str(proj))) if cwd else bash(proj, cmd)
    assert r.returncode == 2, cmd


def test_known_cd_targets_keep_the_start_base(proj, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere")
    fixes = proj / ".superlite" / "fixes"
    notes = (f"mkdir -p {fixes} && cd {fixes} && cat > F-T5-1.md <<'EOF'\n# F-T5-1\nEOF\n"
             "cat > F-T5-2.md <<'EOF'\n# F-T5-2\nEOF\n")
    assert at(proj, notes, outside).returncode == 0   # the transcript form: the cwd outside the project
    assert at(proj, notes, proj).returncode == 0      # #122: `mkdir -p X && cd X` counts as reaching X
    assert at(proj, notes.replace("mkdir -p", "mkdir"), proj).returncode == 2   # plain mkdir may fail: F-T5-2.md at the root
    assert at(proj, f"echo x; cd {proj}/src; echo y > a.py", outside).returncode == 2
    assert at(proj, f"eval \"cd {proj}/src\"; echo x > a.py", outside).returncode == 2


@pytest.mark.parametrize("cmd,cwd", [
    # an unknown directory: a relative path with .. may climb into the project from anywhere
    ("cd .superlite/fixes && cd .. && echo x > ../src/a.py", None),
    ("pushd .superlite && echo x > ../src/a.py", None),
    ("bash -c \"cd .superlite && echo x > ../src/a.py\"", None),
    ("cd .superlite/fixes && cd .. && python3 -c \"open('../src/a.py','w').write('x')\"", None),
    # env -C and sudo -D run their command elsewhere
    ("env -C PROJ/src tee a.py < /tmp/x", "PROJ/.superlite"),
    ("env -C PROJ/src sh -c 'echo x > a.py'", "PROJ/.superlite"),
    ("sudo -D PROJ/src tee a.py < /tmp/x", "PROJ/.superlite"),
    # a wrapper's own options are not the command it runs
    ("env -i tee src/a.py < /tmp/x", None),
    ("sudo -u root tee src/a.py < /tmp/x", None),
    ("env -u HOME sed -i s/a/b/ src/a.py", None),
])
def test_unknown_directory_forms_stay_blocked(proj, cmd, cwd):
    (proj / ".superlite" / "fixes").mkdir()
    (proj / "src").mkdir()
    cmd = cmd.replace("PROJ", str(proj))
    r = at(proj, cmd, cwd.replace("PROJ", str(proj))) if cwd else bash(proj, cmd)
    assert r.returncode == 2, cmd


def test_project_dir_variable_in_a_cd_target(proj):
    (proj / ".superlite" / "fixes").mkdir()
    assert bash(proj, "cd \"$CLAUDE_PROJECT_DIR/.superlite/fixes\" && echo x > F-1.md").returncode == 0
    assert bash(proj, "cd $CLAUDE_PROJECT_DIR/.superlite/fixes && echo x > F-1.md").returncode == 0
    assert bash(proj, "cd \"${CLAUDE_PROJECT_DIR}/src\" && echo x > a.py").returncode == 2


def test_human_gate_relative_cd_after_a_write(tmp_path):
    proj = human_proj(tmp_path)
    assert bash(proj, "echo x > src/a.py; cd .superlite").returncode == 2


def test_submodule_inside_a_linked_worktree_is_no_worktree_root(proj):
    wt = worktree(proj)
    sub = wt / "vendor" / "lib"
    sub.mkdir(parents=True)
    (sub / ".git").write_text(f"gitdir: {proj}/.git/worktrees/wt/modules/lib\n")
    assert run(proj, "Write", {"file_path": str(sub / "docs" / "plans" / "p.md")}).returncode == 2


def test_quoted_later_cd_moves_the_base(proj):
    fixes = proj / ".superlite" / "fixes"
    assert bash(proj, f"mkdir -p \"{fixes}\" && cd \"{fixes}\" && cat > F-T5-1.md <<'EOF'\nx\nEOF").returncode == 0
    assert bash(proj, f"git status && cd '{fixes}' && echo x > F-1.md").returncode == 0
    (proj / "src").mkdir()
    assert bash(proj, f"git status && cd \"{proj}/src\" && echo x > docs/plans/a.md").returncode == 2


def test_commands_before_a_later_cd_keep_the_cwd(proj):
    (proj / "src").mkdir()
    assert at(proj, f"echo x > docs/plans/a.md && cd {proj} && echo y > docs/plans/b.md", proj / "src").returncode == 2


def test_inside_cwd_and_relative_cd_are_the_base(proj):
    (proj / "src").mkdir()
    (proj / "docs").mkdir()
    assert at(proj, "echo x > progress.md", proj / ".superlite").returncode == 0
    assert at(proj, "echo x > docs/plans/a.md", proj / "src").returncode == 2
    assert bash(proj, "cd docs && echo x > plans/a.md").returncode == 0
    assert bash(proj, "cd src && echo x > a.py").returncode == 2


# Case 2: paths in a linked worktree inside the project are judged from that worktree's root.
def test_linked_worktree_paths_judged_from_its_root(proj):
    wt = worktree(proj)
    assert run(proj, "Write", {"file_path": str(wt / "docs" / "plans" / "p.md")}).returncode == 0
    assert run(proj, "Write", {"file_path": str(wt / "src" / "a.py")}).returncode == 2
    assert run(proj, "Write", {"file_path": ".claude/worktrees/wt/docs/plans/p.md"}).returncode == 0
    assert run(proj, "Write", {"file_path": ".claude/worktrees/wt/.superlite/progress.md"}).returncode == 0
    r = run(proj, "Write", {"file_path": str(wt / ".superlite" / "orchestrator.json")})
    assert r.returncode == 2 and "never written directly" in r.stderr
    assert run(proj, "Write", {"file_path": str(wt / "docs" / ".." / "src" / "a.py")}).returncode == 2
    cmd = "python3 - <<'EOF'\nimport pathlib\np=pathlib.Path(\"docs/plans/a.md\"); s=p.read_text()\np.write_text(s)\nEOF"
    assert at(proj, cmd, wt).returncode == 0
    assert at(proj, cmd.replace("docs/plans/a.md", "src/a.py"), wt).returncode == 2


def test_folder_that_is_no_linked_worktree_keeps_project_paths(proj):
    sub = proj / "vendor" / "lib"
    sub.mkdir(parents=True)
    (sub / ".git").write_text("gitdir: ../../.git/modules/lib\n")   # a submodule, not a worktree
    assert run(proj, "Write", {"file_path": str(sub / "docs" / "plans" / "p.md")}).returncode == 2
    assert run(proj, "Write", {"file_path": str(proj / "plain" / "docs" / "plans" / "p.md")}).returncode == 2


def test_human_gate_allows_review_plan_in_linked_worktree(tmp_path):
    proj = human_proj(tmp_path)
    wt = worktree(proj, "wishes")
    plan = wt / "docs" / "superpowers" / "plans" / "2026-11-03-wishes.review.md"
    assert run(proj, "Write", {"file_path": str(plan)}).returncode == 0
    assert run(proj, "Write", {"file_path": str(wt / "docs" / "plans" / "p.md")}).returncode == 2
    assert run(proj, "Write", {"file_path": str(wt / "src" / "a.py")}).returncode == 2


# Case 3a: a docs.md (Noridocs) in any folder is documentation.
def test_docs_md_anywhere_allowed_during_a_run(proj):
    for p in ("Packages/Kit/Sources/AppFeatures/docs.md", "docs.md", str(proj / "src" / "docs.md")):
        assert run(proj, "Write", {"file_path": p}).returncode == 0, p
    for p in ("Packages/Kit/README.md", "Packages/Kit/mydocs.md", "Packages/Kit/docs.md.bak", "src/docs.md/a.py"):
        assert run(proj, "Write", {"file_path": p}).returncode == 2, p
    cmd = f"cd {proj} && python3 -I - Packages/Kit/Sources/AppFeatures/docs.md <<'EOF'\n" + PY_SRC
    assert bash(proj, cmd).returncode == 0


def test_docs_md_stays_blocked_by_the_human_gate(tmp_path):
    proj = human_proj(tmp_path)
    assert run(proj, "Write", {"file_path": "Packages/Kit/docs.md"}).returncode == 2


# #64 limit 3: a mode-first Path(x).open('w') is a writer call.
@pytest.mark.parametrize("call,code", [
    ("Path('src/a.py').open('w').write('x')", 2), ("Path('src/a.py').open('rb+')", 2),
    ("Path('src/a.py').open(mode='a')", 2), ("Path('docs/plans/a.md').open('w').write('x')", 0),
    ("print(Path('src/a.py').open().read())", 0), ("print(Path('src/a.py').open('r').read())", 0),
])
def test_mode_first_path_open(proj, call, code):
    assert bash(proj, f"python3 -c \"from pathlib import Path; {call}\"").returncode == code


# A cd sent to the background (`cd dir &`) moves nothing the later commands see.
def test_background_cd_moves_nothing(proj):
    assert bash(proj, "cd /tmp & echo x > src/a.py").returncode == 2
    assert bash(proj, "cd /tmp && echo x > a.py").returncode == 0
    assert bash(proj, "sleep 1 & echo x > /tmp/a.txt").returncode == 0


def test_hooks_doc_names_accepted_limits():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text()
    line = [x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`")][0]
    for s in ("docs.md", "worktree", "quadratic", "nested quotes"):
        assert s in line, s


# --- #478: arithmetic is no command, redirect or heredoc; only its substitutions run ---------------------------------
import sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

sys.path.insert(0, str(_Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_lex  # noqa: E402


def test_dollar_arith_keeps_its_text_and_only_its_substitutions():
    (s,) = guard_lex.split("echo $(( $(date +%s) - start ))")
    assert s.words == ["echo", "$(( $(date +%s) - start ))"] and s.dyn == [False, True]
    assert s.bodies == ["date +%s"] and s.redirects == []
    (s,) = guard_lex.split('echo "t $(( $(date) - s ))s"')
    assert s.words == ["echo", "t $(( $(date) - s ))s"] and s.bodies == ["date"]
    (s,) = guard_lex.split("echo $((a>b)) $((c<<2)) ${x:-$((d>e))}")
    assert s.bodies == [] and s.redirects == [] and s.heredocs == []


def test_arith_command_and_for_header():
    (s,) = guard_lex.split("(( n > 3 ))")
    assert (s.words, s.redirects, s.subshell, s.arith) == ([], [], None, " n > 3 ")
    segs = guard_lex.split("for (( i=0; i>5; i++ )); do :; done")
    assert segs[0].words == ["for"] and segs[0].arith == " i=0; i>5; i++ " and segs[0].subshell is None
    segs = guard_lex.split("if (( $(date +%s) > 3 )); then :; fi")
    assert segs[0].words == ["if"] and segs[0].bodies == ["date +%s"] and segs[0].redirects == []


def test_unbalanced_double_paren_stays_a_substitution_or_group():
    (s,) = guard_lex.split("x=$((echo hi > a) )")
    assert s.bodies == ["(echo hi > a) "]
    (s,) = guard_lex.split("((echo a) )")
    assert s.subshell == "(echo a)" and s.arith is None


def test_unquoted_heredoc_arith_runs_only_its_substitution():
    (s,) = guard_lex.split("cat > /tmp/b99.txt <<EOF\nelapsed $(( $(date +%s) - start ))\nEOF")
    assert s.bodies == ["date +%s"]


@pytest.mark.parametrize("cmd", [
    "start=$(date +%s); sleep 0; echo \"took $(( $(date +%s) - start ))s\"",
    "start=$(date +%s); x=$(( $(date +%s) - start )); echo $x",
    "start=$(date +%s); CI=true Scripts/ci.sh ios-test > /tmp/b99-ci.log 2>&1; code=$?; "
    "echo \"exit=$code seconds=$(( $(date +%s) - start ))\"",
    "echo $((a>b)) $((c<<2))",
    "(( n > 3 )) && echo ok",
    "for (( i=0; i>5; i++ )); do :; done",
    "while (( n > 0 )); do n=$((n-1)); done",
    "start=1; cat > /tmp/b99.txt <<EOF\nelapsed $(( $(date +%s) - start ))\nEOF",
])
def test_arithmetic_is_no_write_target(proj, cmd):
    assert bash(proj, cmd).returncode == 0, cmd


@pytest.mark.parametrize("cmd", [
    "echo $(( $(echo 1 | tee src/a.py) + 1 ))",
    "(( $(echo 1 > src/a.py) ))",
    "echo $(( 1 + 2 )) > src/a.py",
    "x=$((echo hi > src/a.py) )",
    "((echo hi > src/a.py) )",
    "v=.superlite/a; while (( v++ < 3 )); do :; done; echo > $v",
])
def test_arithmetic_keeps_real_writes_blocked(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


# --- #458: a heredoc script writing below tempfile's temp root ---------------------------------------------------
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

from test_block_coordinator_edits import BASH, HOOK  # noqa: E402

TMP_PROG = "import tempfile, os\nd = tempfile.mkdtemp()\nopen(os.path.join(d, 'a.txt'), 'w').write('x')\n"


def hook_tmpdir(proj, cmd, tmpdir):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "TMPDIR": str(tmpdir)}
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def test_heredoc_script_writing_below_the_temp_root_passes(proj, tmp_path_factory):
    troot, s = tmp_path_factory.mktemp("troot"), tmp_path_factory.mktemp("scratch")
    cmd = f"S={s}; cat > $S/x.py <<'EOF'\n{TMP_PROG}EOF\npython3 $S/x.py"
    assert hook_tmpdir(proj, cmd, troot).returncode == 0
    gettemp = cmd.replace("d = tempfile.mkdtemp()", "d = tempfile.gettempdir()")
    assert hook_tmpdir(proj, gettemp, troot).returncode == 0
    inline = "python3 -c \"" + TMP_PROG.replace("\n", "; ") + "\""
    assert hook_tmpdir(proj, inline, troot).returncode == 0


@pytest.mark.parametrize("change", [
    ("d = tempfile.mkdtemp()", "d = tempfile.mkdtemp(dir='src')"),
    ("import tempfile, os", "import tempfile, os\ntempfile.tempdir = 'src'"),
    ("S=", "export TMPDIR=PROJ/src; S="),
])
def test_temp_root_with_a_named_folder_stays_unknown(proj, tmp_path_factory, change):
    troot, s = tmp_path_factory.mktemp("troot"), tmp_path_factory.mktemp("scratch")
    cmd = f"S={s}; cat > $S/x.py <<'EOF'\n{TMP_PROG}EOF\npython3 $S/x.py"
    cmd = cmd.replace(change[0], change[1], 1).replace("PROJ", str(proj))
    assert hook_tmpdir(proj, cmd, troot).returncode == 2, cmd


# F-T1-1: a failing `$((` or command-position `((` is tried as arithmetic once per start index, so nesting stays linear.
@pytest.mark.parametrize("cmd", [
    "echo " + "$(( (" * 40 + ")" * 40,
    "echo " + "$(( (" * 40 + "rm src/a.py" + ")" * 40,
    "((" * 40 + "echo a" + ")" * 40,
    "(( " + "$(( (" * 40 + ")" * 40,
    "(( " * 40 + "rm src/a.py" + ") " * 40,
])
def test_nested_failing_arithmetic_lexes_in_linear_time(cmd):
    code = "import sys, guard_lex; guard_lex.split(sys.argv[1])"
    env = {**os.environ, "PYTHONPATH": str(_Path(guard_lex.__file__).parent)}
    subprocess.run([sys.executable, "-c", code, cmd], env=env, timeout=1.0, check=True)  # TimeoutExpired = exponential


def test_nested_failing_arithmetic_keeps_the_hook_verdict(proj):
    def verdict(cmd):
        raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
        return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, timeout=10).returncode

    assert verdict("echo " + "$(( (" * 40 + ")" * 40) == 2  # nested past the judge's depth: an unknown target, blocked as before
    assert verdict("echo " + "$(( (" * 40 + "echo 1 > src/a.py" + ")" * 40) == 2


# #693: runs the script judge must keep letting through.
def _src(proj):
    (proj / "src").mkdir(exist_ok=True)
    (proj / "src" / "a.py").write_text("x = 1\n")


@pytest.mark.parametrize("cmd", [
    "bash script.sh", "python3 nothere.py", "./nothere.sh", "python3 -m pytest -q", "uv run pytest -q",
])
def test_693_missing_and_module_runs_pass(proj, cmd):
    _src(proj)
    assert bash(proj, cmd).returncode == 0


def test_693_tracked_script_passes(proj):
    _src(proj)
    (proj / "tools").mkdir()
    w = proj / "tools" / "w.sh"
    w.write_text("echo y > src/a.py\n")
    w.chmod(0o755)
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    subprocess.run(["git", "add", "tools/w.sh"], cwd=proj, check=True)
    assert bash(proj, "bash tools/w.sh").returncode == 0
    assert bash(proj, "./tools/w.sh").returncode == 0


def test_693_old_untracked_script_passes(proj, tmp_path_factory):
    import datetime
    import time
    _src(proj)
    now = time.time()
    stamp = datetime.datetime.fromtimestamp(now - 3600, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t = proj / "t.jsonl"
    t.write_text(json.dumps({"type": "user", "timestamp": stamp}) + "\n")
    old = tmp_path_factory.mktemp("old") / "old.sh"
    old.write_text("echo y > src/a.py\n")
    os.utime(old, (now - 7200, now - 7200))
    assert run(proj, "Bash", {"command": f"bash {old}"}, transcript_path=str(t)).returncode == 0


@pytest.mark.parametrize("cmd", [
    "eval \"$(ssh-agent -s)\"", "eval 'ls'", "eval ls -la", "x='ls docs'; eval \"$x\"",
    "eval \"$(cat)\" <<'EOF'\nls\nEOF",
])
def test_693_eval_forms_pass(proj, cmd):
    _src(proj)
    assert bash(proj, cmd).returncode == 0


def test_693_quoted_tmpdir_with_space_passes(proj, tmp_path_factory):
    _src(proj)
    d = tmp_path_factory.mktemp("tmp") / "a b"  # proj is tmp_path itself: the folder must lie outside it
    d.mkdir()
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": 'echo x > "$TMPDIR/o.txt"'}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "TMPDIR": str(d)}
    r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)
    assert r.returncode == 0


def test_693_binary_and_activate_pass(proj, tmp_path_factory):
    _src(proj)
    app = tmp_path_factory.mktemp("bin") / "app"
    app.write_bytes(b"\x7fELF" + b"\0" * 64)
    app.chmod(0o755)
    assert bash(proj, f"{app} --version").returncode == 0
    (proj / ".venv" / "bin").mkdir(parents=True)
    (proj / ".venv" / "bin" / "activate").write_text("export X=1\n")
    assert bash(proj, "source .venv/bin/activate").returncode == 0
