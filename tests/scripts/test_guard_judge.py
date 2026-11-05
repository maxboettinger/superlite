import io
import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_files  # noqa: E402
import guard_judge  # noqa: E402
import guard_tools  # noqa: E402
from guard_judge import Verdict, judge, main  # noqa: E402

REAL = os.environ.get("SUPERLITE_REAL") == "1"
_WORDS = re.compile(r"\S+")


def _fake_files(words):  # one operand per path, like the real cp/mv/rm/tee/touch for the plain forms used here
    ops = [w for w in words[1:] if not w.startswith("-")]
    if words[0] == "cp":
        return ops[-1:]
    return ops


def _fake_tools(words, **_ctx):  # Python open(..., 'w') with a literal target; a non-literal target is "?"
    if words[0] != "python3" or "-c" not in words:
        return []
    code = words[words.index("-c") + 1]
    lit = re.findall(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][wax]", code)
    return lit or (["?"] if re.search(r"open\([^'\"]", code) else [])


@pytest.fixture(autouse=True)
def parts(monkeypatch):
    """Swappable fakes of guard_files and guard_tools (T2, T3): fakes by default, the real modules when SUPERLITE_REAL=1.
    The lexer (T1) is pure and ran before T4: it is always the real one."""
    if not REAL:
        monkeypatch.setattr(guard_files, "targets", _fake_files)
        monkeypatch.setattr(guard_files, "COMMANDS", frozenset({"cp", "mv", "rm", "tee", "touch", "ln", "install"}))
        monkeypatch.setattr(guard_tools, "targets", _fake_tools)
        monkeypatch.setattr(guard_tools, "COMMANDS", frozenset({"python3", "git", "node", "tar"}))


@pytest.fixture
def P(tmp_path):
    root = tmp_path / "p"
    for d in ("src", "docs/plans", ".superlite", "lib"):
        (root / d).mkdir(parents=True)
    (tmp_path / "out").mkdir()
    return str(root.resolve())


def blocked(cmd, P, mode="active", cwd=None):
    v = judge(cmd, cwd or P, P, mode)
    assert v is not None, cmd
    return v


def passes(cmd, P, mode="active", cwd=None):
    assert judge(cmd, cwd or P, P, mode) is None, cmd


def test_examples(P):
    assert judge("printf x > src/a.py", P, P, "active") == Verdict(rel="src/a.py", abs=f"{P}/src/a.py", kind="code")
    assert judge("printf x > docs/plans/a.md", P, P, "active") is None
    assert judge("printf x > src/a.py", P, P, "idle") is None
    assert judge("cd " + P + "/docs && cd ../src && rm a.py", P, P, "active") == Verdict(
        rel="src/a.py", abs=f"{P}/src/a.py", kind="code")
    assert judge("S=/tmp/s; cd $S && cat > A.md", P, P, "active") is None


def test_review_149_walker_items(P, tmp_path):
    out = str(tmp_path / "out")
    # item 3: a redirect of stderr to /dev/null, with a space, is no target and hides no other
    assert blocked("cp /tmp/x src/a.py 2> /dev/null", P).rel == "src/a.py"
    # item 4: a program read from stdin by an eval inside a group takes the heredoc after the group
    assert blocked('{ eval "$(cat)"; } <<EOF\n\nrm src/a.py\nEOF', P).rel == "src/a.py"
    # item 5: an eval's quoted cd changes the directory of the commands after it
    plans = f"{P}/docs/plans"
    assert blocked("eval \"c''d ../../src\"; printf x > a.md", P, cwd=plans).rel == "src/a.md"
    passes('eval "cd ../../docs"; printf x > a.md', P, cwd=plans)
    # 2026-11-05 comments: a second worktree's cd, and a cd through a variable
    for w in ("wtA", "wtB"):  # linked worktrees inside the project: judged from their roots
        (Path(P) / w).mkdir()
        (Path(P) / w / ".git").write_text(f"gitdir: /x/.git/worktrees/{w}\n")
    passes(f"cd {P}/wtA && echo x >> .superlite/progress.md; cd {P}/wtB && ls", P)
    assert blocked(f"cd {P}/wtA && echo x >> src/a.py; cd {P}/wtB && ls", P).kind == "code"
    passes(f"cd {out}/wtA && echo x >> .superlite/progress.md; cd {out}/wtB && ls", P)
    passes(f"S={out}/s; cd $S && cat > A.md", P)
    passes(f'S={out}/s; cd "$S" && cat > A.md', P)
    assert blocked(f"S={P}/src; cd $S && cat > A.md", P).rel == "src/A.md"
    assert blocked("cd $X && cat > A.md", P).rel == "A.md"  # unknown directory: judged from the project root


def test_cd_state_per_subshell(P):
    passes("(cd src) && printf x > docs/a.md", P)
    passes("pushd src && popd && printf x > docs/a.md", P)
    passes("cd src; cd -; printf x > docs/a.md", P)
    assert blocked("cd src && printf x > a.md", P).rel == "src/a.md"
    # a cd in a pipeline or a background job does not move the shell
    passes("cd src | cat; printf x > docs/a.md", P)
    passes("cd src & printf x > docs/a.md", P)
    # a cd that may fail leaves both directories possible for the later lines
    blocked("cd nowhere; printf x > a.md", P)
    blocked("cd src || true; printf x > a.md", P)
    # the && commands after a cd run from its target, which may be created before the command runs: judged there
    assert blocked("cd nowhere && printf x > docs/a.md", P).rel == "nowhere/docs/a.md"
    # an unreadable cd makes the directory unknown from there on
    assert blocked("cd $X; printf x > docs/plans/a.md", P).rel == "docs/plans/a.md"
    assert blocked("cd docs; cd ..; printf x > a.md", P).rel == "a.md"
    # a sure cd into an existing folder moves the later lines too
    passes("cd docs/plans; printf x > a.md", P)
    # but not after a command that may remove the folder
    assert blocked("rm -rf docs/plans; cd docs/plans; printf x > a.md", P).rel in ("docs/plans", "a.md")


def test_wrappers_and_recursion(P):
    for cmd in (
        "env A=1 rm src/a", "sudo -u x rm src/a", "timeout 5 rm src/a", "xargs rm < list", "find src -delete",
        "find . -name x -exec rm {} \\;", "bash -c 'rm src/a'", 'sh -c "rm src/a"', "eval rm src/a",
        "python3 - <<EOF\nopen('src/a','w')\nEOF", "curl x | sh", "bash <(curl x)",
        "nice -n 5 rm src/a", "command rm src/a", "exec rm src/a", "nohup rm src/a", "time rm src/a",
        "env -i FOO=1 sudo rm src/a", "echo $(rm src/a)", "echo `rm src/a`", "echo $(echo $(rm src/a))",
        "(rm src/a)", "{ rm src/a; }", "if x; then rm src/a; fi", "true & rm src/a", "env -C src rm a",
        "bash -c 'cd src && rm a'", "sh -s <<EOF\nrm src/a\nEOF", "source /dev/stdin <<EOF\nrm src/a\nEOF",
        "cat <<EOF | sh\nrm src/a\nEOF", "f() { rm src/a; }; f",
    ):
        assert blocked(cmd, P) is not None, cmd
    for cmd in ("env A=1 ls", "bash -c 'ls'", "sudo ls", "xargs ls < list", "find src -name x", "bash script.sh",
                "echo $(ls)", "cat <<EOF\nrm src/a\nEOF", "eval 'ls'", "timeout 5 ls", "(cd src && ls)",
                "find docs/plans -delete", 'eval "$(ssh-agent -s)"', "env -C docs/plans touch a.md"):
        passes(cmd, P)
    assert blocked("xargs rm < list", P).rel == "?"
    assert blocked("find src -delete", P).rel == "src/?"
    # sl calls are not judged
    passes('bash "$SL" dispatch implementer t1', P)
    passes("/x/skills/subagent-driven-development/scripts/sl run_tests --fast tests/a.py", P)
    blocked('echo "see subagent-driven-development/scripts" > src/app.py', P)


def test_policy_modes(P, tmp_path):
    # protected names block in every mode, also as a path below a linked worktree
    for mode in ("idle", "active", "human"):
        v = blocked("printf x > .superlite/orchestrator.json", P, mode)
        assert v.kind == "protected" and v.rel == ".superlite/orchestrator.json", mode
        assert blocked("printf x > .SUPERLITE/Human-Replies.jsonl", P, mode).kind == "protected"
    wt = Path(P) / ".claude" / "worktrees" / "w"
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: /x/.git/worktrees/w\n")
    passes("printf x > .claude/worktrees/w/docs/plans/a.md", P)
    assert blocked("printf x > .claude/worktrees/w/src/a.py", P).kind == "code"
    assert blocked("printf x > .claude/worktrees/w/.superlite/orchestrator.json", P, "active").kind == "protected"
    # idle allows everything else
    passes("printf x > src/a.py; rm -rf src", P, "idle")
    # human mode allows only review plans and .superlite
    passes("printf x > docs/plans/x.review.md", P, "human")
    passes("printf x > .superlite/progress.md", P, "human")
    assert blocked("printf x > docs/plans/x.md", P, "human").kind == "human"
    assert blocked("printf x > docs/a.md", P, "human").kind == "human"
    # active mode allowed set
    for ok in ("docs/plans/a.md", "docs/x/plans/a.md", "docs/a/b.md", "SPEC.md", "sub/SPEC-1.md", "docs.md", "sub/docs.md",
               ".superlite/a/b", ".git/info/exclude"):
        passes(f"printf x > {ok}", P)
    for bad in ("docs/a.txt", "src/SPEC.py", ".git/config", ".git/info/exclude.bak", "docs/../src/a.py"):
        assert blocked(f"printf x > {bad}", P).kind == "code", bad
    # outside the project
    passes("printf x > /tmp/x", P)
    passes("printf x > ../outside/x", P)
    passes("printf x > /dev/null", P)
    passes("printf x 2>&1", P)
    passes(f"printf x > {tmp_path}/out/x", P)
    assert blocked(f"printf x > {P}/src/a.py", P).abs == f"{P}/src/a.py"
    # a cwd outside the project makes relative targets outside; a cwd inside makes them inside
    passes("printf x > src/a.py", P, cwd=str(tmp_path / "out"))
    assert blocked("printf x > a.py", P, cwd=f"{P}/src").rel == "src/a.py"
    # the project root itself is a target of a tree-wide rewrite
    if REAL:
        assert blocked("git reset --hard", P).rel == "."


def test_unknown_targets(P):
    assert blocked("rm \"$X\"", P).rel == "?"
    assert blocked("python3 -c \"p=input(); open(p,'w')\"", P).rel == "?"
    passes("rm \"$X\"", P, "idle")
    assert blocked("rm \"$X\"; cat .superlite/orchestrator.json", P, "idle").rel == "?"
    passes(f"X={P}/docs/plans/a.md; rm \"$X\"", P)
    passes("rm ~/x", P)
    blocked('rm "$HOME/x y"', P)  # parity (test_guard_targets): $HOME is not resolved
    passes("rm $CLAUDE_PROJECT_DIR/.superlite/x ${CLAUDE_PROJECT_DIR}/docs/plans/y".replace("$CLAUDE_PROJECT_DIR", P).replace("${CLAUDE_PROJECT_DIR}", P), P)
    assert blocked("rm $CLAUDE_PROJECT_DIR/src/a ${X}", P).rel in ("?", "src/a")


def test_parity_walker_fixes(P, tmp_path):
    """T5 parity: the old guard's cd, loop, script and stdin rules, as the existing suites pin them."""
    out = str(tmp_path / "out")
    sl = f"{P}/.superlite"
    passes(f"echo a; mkdir -p {sl}/a/b && cd {sl}/a && echo x > F.md; echo y > G.md", P)  # mkdir -p makes each parent
    for cmd, cwd in (
        (f"{{ false; }} && cd {sl}; echo x > a.py", None),
        ("echo a > .superlite/n; mkdir -p .superlite/n && cd .superlite/n; echo y > a.py", None),
        (f"export CDPATH={P}/src; mkdir -p docs/plans/x && cd docs/plans/x && echo x > a.py", None),
        (f"! cd {sl}/nope && echo x > src/a.py", None),
        (f"for i in 1 2; do echo x > a.py; cd {P}/src; done", out),
        (f"f(){{ echo x > a.py; }}; cd {P}/src; f", sl),
        (f"cd {out} && cd .. && rm src/a.py", out),
        (f"cd {out} && cd - && rm src/a.py", out),
        (f"cd {out} && python3 -c \"import os; os.chdir('{P}'); open('src/a.py','w')\"", None),
        ("X=a.py; X=docs/plans/p.md; rm \"$X\"", None),
        (f"cat > {out}/x.py <<'EOF'\nimport sys\nopen(sys.argv[1],'w')\nEOF\npython3 {out}/x.py src/a.py", None),
        ("bash -c 'cd /tmp; echo x > docs/plans/a.md'", None),
        ("bash -c 'source /dev/stdin' <<'EOF'\nrm src/a.py\nEOF", None),
        ("bash -euo pipefail <<'EOF'\nrm src/a.py\nEOF", None),
        (f"cd {P}/docs/plans && ls; c''d {P}/src; cd {P}/docs/plans; rm a.md", None),
    ):
        blocked(cmd, P, cwd=cwd)
    passes(f"cat > {out}/x.py <<'EOF'\nimport sys\nopen(sys.argv[1],'w')\nEOF\npython3 {out}/x.py docs/plans/x.md", P)
    passes("cat <<'EOF' | sh\necho hi\nEOF", P)
    passes(f"cd {P}; source .venv/bin/activate; echo x > .superlite/out.json", P)
    assert blocked("python3 -c \"p=input(); open(p,'w')\" # orchestrator.json", P).kind == "protected"
    assert blocked("ls | cat; cd nope; printf x > human-replies.jsonl", P, "idle").kind == "protected"
    nox = Path(sl) / "nox"
    nox.mkdir()
    nox.chmod(0o600)
    try:
        blocked(f"cd {nox}; echo a; cd {nox}; echo x > a.py", P)
    finally:
        nox.chmod(0o700)


def test_partial_targets(P, tmp_path, monkeypatch):
    """A target with an unknown part ("?" component): outside passes unless the folder holds the project."""
    monkeypatch.setattr(guard_tools, "targets", lambda w, **_: [w[-1]] if w[0] == "python3" else [])
    passes("python3 /tmp/s/?", P)
    blocked(f"python3 {tmp_path}/?", P)  # tmp_path holds the project
    blocked("python3 src/?", P)
    passes("python3 .superlite/?", P)
    blocked("python3 ?/orchestrator.json", P, "idle")


def test_main_cli(P, tmp_path, monkeypatch, capsys):
    sd = tmp_path / "sd"
    sd.mkdir()
    argv = ["--mode", "active", "--project", P, "--sd", str(sd)]

    def run(stdin):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        code = main(argv)
        cap = capsys.readouterr()
        return code, cap.out, cap.err

    hook = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm src/a"}, "cwd": P})
    code, out, err = run(hook)
    assert code == 2 and out == ""
    assert "must not write project code" in err and "fixer-sonnet" in err
    assert err.splitlines()[-2:] == [f"Absolute target: {P}/src/a", "Blocked target: src/a"]
    rows = [json.loads(line) for line in (sd / "incidents.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["kind"] == "rule-block" and rows[0]["agent"] == "coordinator"
    assert rows[0]["tool"] == "Bash" and rows[0]["target"] == "src/a"

    ok = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm docs/plans/a.md"}, "cwd": P})
    assert run(ok) == (0, "guard: ok\n", "")  # the ack the hook needs before it trusts an exit 0
    monkeypatch.setenv("SUPERLITE_GUARD_NONCE", "n42")
    assert run(ok) == (0, "guard: ok n42\n", "")
    monkeypatch.delenv("SUPERLITE_GUARD_NONCE")
    assert len((sd / "incidents.jsonl").read_text().splitlines()) == 1

    code, out, err = run(json.dumps({"tool_name": "PowerShell", "tool_input": {"command": "printf x > src/b"}, "cwd": P}))
    assert code == 2 and rows[0]["tool"] == "Bash" and "PowerShell" in (sd / "incidents.jsonl").read_text()

    prot = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm .superlite/orchestrator.json"}, "cwd": P})
    code, out, err = run(prot)
    assert code == 2 and "never written directly" in err and "Blocked target" not in err

    unk = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm \"$X\""}, "cwd": P})
    code, out, err = run(unk)
    assert code == 2 and err.splitlines()[-1] == 'Blocked command: rm "$X"'

    human = ["--mode", "human", "--project", P, "--sd", str(sd)]
    monkeypatch.setattr(sys, "stdin", io.StringIO(hook))
    assert main(human) == 2
    assert "Human orchestrator" in capsys.readouterr().err

    before = len((sd / "incidents.jsonl").read_text().splitlines())
    for bad in ("", "not json", "[]", json.dumps({"tool_name": "Bash"}), json.dumps({"tool_name": "Bash", "tool_input": []})):
        code, out, err = run(bad)
        assert (code, out, err) == (0, "guard: ok\n", ""), bad
    rows = [json.loads(line) for line in (sd / "incidents.jsonl").read_text().splitlines()]
    assert len(rows) == before + 5 and all(r["kind"] == "guard-error" for r in rows[before:])


def test_main_fails_open_on_crash(P, tmp_path, monkeypatch, capsys):
    sd = tmp_path / "sd"
    sd.mkdir()

    def boom(text):
        raise RuntimeError("lexer crashed")

    monkeypatch.setattr(guard_judge.guard_lex, "split", boom)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm src/a"}})))
    assert main(["--mode", "active", "--project", P, "--sd", str(sd)]) == 0
    assert capsys.readouterr() == ("guard: ok\n", "")
    row = json.loads((sd / "incidents.jsonl").read_text().splitlines()[-1])
    assert row["kind"] == "guard-error" and "lexer crashed" in row["target"]


def test_deep_nesting_is_unknown_not_a_crash(P):
    cmd = "echo x"
    for _ in range(12):  # each level doubles the backslashes: 12 levels reach the judge's own depth limit
        cmd = "bash -c " + json.dumps(cmd)
    assert blocked(cmd, P).rel == "?"
    passes("bash -c " + json.dumps("bash -c " + json.dumps("echo x")), P)


def test_variables_reach_interpreter_code(P):
    passes("T=docs/plans/p.md; python3 -c \"open('$T','w')\"", P)
    assert blocked("T=src/a.py; python3 -c \"open('$T','w')\"", P).rel == "src/a.py"
    assert blocked("T=a.py; T=src/a.py; python3 -c \"open('$T','w')\"", P).rel == "src/a.py"
    assert blocked("python3 -c \"open('$U','w')\"", P).rel == "?"


def test_unterminated_heredoc_runs_as_commands(P):
    blocked("cat <<EOF\nrm src/a.py", P)
    passes("cat <<EOF\nrm src/a.py\nEOF", P)
    passes("cat <<-EOF\n\trm src/a.py\n\tEOF", P)


def test_mkdir_then_cd_reaches_the_folder(P):
    passes("mkdir -p .superlite/n && cd .superlite/n && cat > F1.md; cat > F2.md", P)
    (Path(P) / ".superlite" / "f").write_text("a file, so mkdir -p fails\n")
    blocked("mkdir -p .superlite/f && cd .superlite/f; echo y > a.py", P)
    blocked("mkdir -p -m 000 .superlite/n && cd .superlite/n; echo y > a.py", P)
    blocked("mkdir -p .superlite/m && cd .superlite/n; echo y > a.py", P)


def test_a_cd_that_may_not_run_leaves_both_directories(P):
    blocked("if false; then cd docs; fi; printf x > a.py", P)
    blocked("for d in x; do\ncd docs\ndone; printf x > a.py", P)
    blocked("{ false; } && cd docs; printf x > a.py", P)
    blocked("f() { cd docs; }; f; printf x > a.py", P)
    blocked(f"rm -rf docs/plans; cd {P}/docs/plans; printf x > a.py", P)
    blocked("cd docs; eval \"$X\"; printf x > a.py", P)
    blocked("cd docs; source ./s.sh; printf x > a.py", P)
    blocked("cd docs; alias cd=true; printf x > a.py", P)
    passes("cd docs/plans; printf x > a.md", P)


def test_argv_words_reach_interpreter_code(P):
    body = "<<'EOF'\nimport sys\nopen(sys.argv[1],'w').write('x')\nEOF"
    passes("python3 - docs/plans/p.md " + body, P)
    assert blocked("python3 - src/a.py " + body, P).rel == "src/a.py"
    assert blocked("python3 - " + body, P).rel == "?"
    assert blocked("python3 - docs/plans/p.md <<'EOF'\nimport sys\nopen(sys.argv[2],'w')\nEOF", P).rel == "?"
    passes("T=docs/plans/p.md; python3 - \"$T\" " + body, P)
    assert blocked("T=src/a.py; python3 - \"$T\" " + body, P).rel == "src/a.py"


def test_glob_and_brace_targets_are_patterns(P, tmp_path):
    # final review 1: a glob or brace target is not judged as the literal text `.superlite/*` or `docs/plans/*` matches
    for mode in ("active", "idle", "human"):
        for cmd in ("printf '{\"mode\":\"human\",\"approved\":true}' > .superlite/orchestrator.jso?",
                    "tee .superlite/{orchestrator.json,x}", "rm .superlite/orch*", "rm .superlite/*",
                    "rm .superlite/{orchestrator.json}", "cd .superlite && rm orch*", "rm .superl*/human-replies.jsonl"):
            assert blocked(cmd, P, mode).kind == "protected", (mode, cmd)
    assert blocked("touch docs/plans/{x,../../src/a.py}", P).rel == "src/a.py"
    assert blocked("touch docs/plans/x > docs/plans/{y,../../src/b.py}", P).rel == "src/b.py"  # zsh writes both
    assert blocked("touch src/*.py", P).rel == "src/?"
    assert blocked("touch docs/{1..3}.py", P).rel == "?"
    assert blocked("touch docs/plans/*/../../../src/a.py", P).rel == "?"
    passes("touch docs/plans/{a,b}.md .superlite/*.md docs/plans/*", P)
    passes(f"touch {tmp_path}/out/* {tmp_path}/out/{{a,b}}", P)
    passes("ls src/* && cat .superlite/*.json", P)
    passes("[ -f src/a.py ] && echo yes", P)
    passes("touch src/{a,b}.py", P, "idle")


def test_dynamic_command_word_judges_its_operands(P):
    # final review 2: a command word the guard cannot read may be rm or tee
    for cmd in ("/bin/r? -f src/a.py", "$(echo rm) src/a.py", "${RM:-rm} src/a.py", "{rm,-f} src/a.py"):
        assert blocked(cmd, P).rel == "src/a.py", cmd
    assert blocked("$X .superlite/orchestrator.json", P, "idle").kind == "protected"
    passes("$(echo rm) -f docs/plans/a.md", P)
    passes("$(echo rm) src/a.py", P, "idle")
    passes("RM=rm; $RM docs/plans/a.md", P)


def test_python_cache_is_protected(P, tmp_path, monkeypatch):
    # final review 3: the hook trusts ~/.cache/superlite/python; a fake interpreter there would pass every command
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("SUPERLITE_CACHE_DIR", raising=False)
    (tmp_path / "home" / ".cache" / "superlite").mkdir(parents=True)
    for mode in ("idle", "active"):
        assert blocked("printf '/usr/bin/true\\n' > ~/.cache/superlite/python", P, mode).kind == "protected"
        assert blocked("cd ~/.cache/superlite && cp /tmp/x python", P, mode).kind == "protected"
        assert blocked("mv /tmp/python ~/.cache/superlite/", P, mode).kind == "protected"
        assert blocked("rm ~/.cache/superlite/pyth*", P, mode).kind == "protected"
    passes("printf x > ~/.cache/other", P, "idle")


def test_budget_makes_a_runaway_walk_unknown(P):
    # final review 5: re-runs for each earlier value of a variable (and loop re-walks) multiply at every nesting level
    import signal
    import time
    cmd = "echo $X"
    for _ in range(6):
        cmd = "( " + cmd + " )"
    cmd = "".join(f"X=a{i}; " for i in range(16)) + cmd  # 16 values at 6 levels: 16**6 walks without a budget
    alarm = getattr(signal, "SIGALRM", None)
    if alarm is not None:  # the unfixed walk runs for hours: fail instead of hanging
        def stop(*_):
            raise TimeoutError("judge ran past 5 s")
        old = signal.signal(alarm, stop)
        signal.alarm(5)
    try:
        t = time.monotonic()
        v = judge(cmd, P, P, "active")
        took = time.monotonic() - t
    finally:
        if alarm is not None:
            signal.alarm(0)
            signal.signal(alarm, old)
    assert took < 2.0 and v is not None and v.rel == "?", (took, v)
    assert judge(cmd, P, P, "idle") is None


def test_nul_in_a_target_is_unknown(P, tmp_path, monkeypatch, capsys):
    # final review 6: os.path.realpath raises ValueError on a NUL; that was a guard-error and an allow
    assert blocked("printf x > \"a\x00b\"", P).rel == "?"
    assert blocked("cd \"a\x00b\" && cd .. && printf x > c", P).rel == "?"
    sd = tmp_path / "sd"
    sd.mkdir()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm 'a\u0000b'"}})))
    assert main(["--mode", "active", "--project", P, "--sd", str(sd)]) == 2
    assert "guard-error" not in (sd / "incidents.jsonl").read_text()
