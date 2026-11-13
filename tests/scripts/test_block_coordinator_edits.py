import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "pool.json").write_text("{}")
    return tmp_path


def run(proj, tool, tool_input, raw=None, **extra):
    if raw is None:
        raw = json.dumps({"tool_name": tool, "tool_input": tool_input, **extra})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def bash(proj, cmd, tool="Bash"):
    return run(proj, tool, {"command": cmd})


def test_blocks_coordinator_edit_of_source(proj):
    for tool in ("Edit", "Write"):
        r = run(proj, tool, {"file_path": str(proj / "src" / "app.py")})
        assert r.returncode == 2
    assert run(proj, "NotebookEdit", {"notebook_path": str(proj / "a.ipynb")}).returncode == 2
    assert run(proj, "Write", {"file_path": "src/main.rs"}).returncode == 2
    assert run(proj, "Write", {"file_path": str(proj / "pyproject.toml")}).returncode == 2


def test_message_names_fixer_tiers(proj):
    r = run(proj, "Edit", {"file_path": str(proj / "a.go")})
    for s in ("fixer-sonnet", "fixer-sonnet-high", "fixer-opus",
              "F-<Tn>-<n>", ".superlite/fixes/", "implementer-haiku", "fixing.md"):
        assert s in r.stderr
    incidents = (proj / ".superlite" / "incidents.jsonl").read_text().splitlines()
    assert json.loads(incidents[0])["kind"] == "rule-block"


def test_subagent_allowed(proj):
    r = run(proj, "Edit", {"file_path": str(proj / "src" / "app.py")}, agent_id="a1", agent_type="implementer")
    assert r.returncode == 0 and r.stderr == ""
    assert bash(proj, "sed -i s/a/b/ src/app.py").returncode == 2
    r = run(proj, "Bash", {"command": "sed -i s/a/b/ src/app.py"}, agent_id="a1")
    assert r.returncode == 0


def test_allowed_paths(proj):
    for p in ("docs/plans/x/plan.md", "SPEC.md", "SPEC-v2.md", "docs/guide.md", "docs/a/b/c.md",
              ".superlite/progress.md", ".superlite/fixes/F-T1-1.md", ".superlite/briefs/t1.md",
              str(proj / "docs" / "plans" / "p.md"), "/elsewhere/outside/file.py"):
        assert run(proj, "Write", {"file_path": p}).returncode == 0, p
    assert run(proj, "Write", {"file_path": "docs/code.py"}).returncode == 2


def test_inactive_run_allowed(tmp_path):
    assert run(tmp_path, "Edit", {"file_path": str(tmp_path / "a.py")}).returncode == 0
    assert bash(tmp_path, "sed -i s/a/b/ a.py").returncode == 0


def test_stable_json_marker_activates_before_wave_0(tmp_path):
    # lint --stable writes stable.json before Wave 0, so the guard is already on when the skeleton is written.
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "stable.json").write_text("{}")
    assert run(tmp_path, "Write", {"file_path": "pyproject.toml"}).returncode == 2


def test_prime_marker_activates(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "prime.md").write_text("x")
    assert run(tmp_path, "Edit", {"file_path": "a.py"}).returncode == 2


@pytest.mark.parametrize("cmd", [
    "sed -i 's/a/b/' src/app.py",
    "sed -i.bak s/a/b/ src/app.py",
    "perl -pi -e 's/a/b/' src/app.py",
    "echo hi | tee src/app.py",
    "tee -a src/app.py < /dev/null",
    "echo hi > src/app.py",
    "echo hi >> src/app.py",
    "cat > src/app.py <<'EOF'\nprint(1)\nEOF",
    "cat <<EOF > src/app.py\nx\nEOF",
    "python3 -c \"open('src/a.py','w').write('x')\"",
    "node -e \"require('fs').writeFileSync('a.js','x')\"",
    "python - <<'EOF'\nfrom pathlib import Path\nPath('a.py').write_text('x')\nEOF",
    "git apply fix.patch",
    "patch -p1 < fix.patch",
    "mv src/a.py src/b.py",
    "cp /tmp/x.py src/a.py",
    "rm src/a.py",
    "ls && rm -f src/a.py",
    "cp /tmp/x.py src/a.py 2>/dev/null",
    "echo \"multi\nline\" > src/a.py",
    "echo \"x\\\"y\" > src/a.py",
])
def test_blocks_bash_writes(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


def test_blocks_powershell_write(proj):
    assert bash(proj, "'x' | Out-File a.txt > src/a.py", "PowerShell").returncode == 2


@pytest.mark.parametrize("cmd", [
    "cat src/app.py", "grep -rn foo src", "ls -la", "git status", "git log --oneline", "git diff",
    "git commit -m 'fix a > b'", "python3 -m pytest -q", "pytest tests 2>&1 | tail -5",
    "npm test 2>/dev/null", 'bash "$SL" dispatch implementer t1', 'bash "$SL" fix F-T1-1 > .superlite/out.txt',
    "echo hi > .superlite/progress.md", "cat > docs/plans/p.md <<'EOF'\nuse a -> b > c\nEOF",
    "sed -n 1,5p src/app.py", "sed -i s/a/b/ .superlite/progress.md", "echo hi > /dev/null",
    "echo hi > /tmp/x.txt", "cp src/a.py /tmp/a.py", "rm -f /tmp/x", "python3 -c \"print(open('a.py').read())\"",
    "echo \"a > b\"", "tee .superlite/log.txt",
    # Redirects are not cp operands; escaped and multi-line quotes hide their '>'.
    "cp src/a.py /tmp/a.py 2>/dev/null", "grep -E \"href=\\\"[^>]*>\" x.html",
    "grep -c \"<li[^>]*>\nfoo\" x.html",
])
def test_allows_bash_reads_and_safe_writes(proj, cmd):
    r = bash(proj, cmd)
    assert r.returncode == 0, cmd


def test_malformed_input_fails_open(proj):
    for raw in ("", "not json", "[]", json.dumps({"tool_name": "Bash"}),
                json.dumps({"tool_name": "Edit", "tool_input": {}}),
                json.dumps({"tool_name": "Bash", "tool_input": {"command": 5}})):
        r = run(proj, None, None, raw=raw)
        assert r.returncode == 0, raw
        assert r.stdout == "" and r.stderr == ""


def test_other_tools_ignored(proj):
    assert run(proj, "Read", {"file_path": str(proj / "a.py")}).returncode == 0


def test_hooks_json_registers_hook():
    data = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    e = data["hooks"]["PreToolUse"][1]
    assert e["matcher"] == "Edit|Write|NotebookEdit|Bash|PowerShell|Agent"
    assert e["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/block-coordinator-edits"'


def test_hook_has_lf_endings():
    assert b"\r" not in HOOK.read_bytes()


def test_typical_allowed_call_is_fast(proj):
    import time

    def best(argv, raw=""):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
        times = []
        for _ in range(3):
            t = time.perf_counter()
            subprocess.run(argv, input=raw, capture_output=True, text=True, env=env)
            times.append(time.perf_counter() - t)
        return min(times)

    base = best([BASH, "-c", "exit 0"])
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status && ls src"}})
    for hook_raw in (raw, json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x"}, "agent_id": "a"})):
        t = best([BASH, str(HOOK)], hook_raw)
        assert t < max(0.6, base + 0.35), (t, base)


# PIX-837: interpreter writes are judged by their target, not by the interpreter.
@pytest.mark.parametrize("cmd", [
    "python3 - <<'EOF'\nfrom pathlib import Path\np = Path('docs/superpowers/plans/p.md')\np.write_text(p.read_text().replace('a', 'b'))\nEOF",
    "python3 -c \"import json; d=json.load(open('.superlite/pool.json')); open('.superlite/pool.json','w').write(json.dumps(d))\"",
    "python3 -c \"open('docs/superpowers/plans/p.incidents.jsonl','a').write('x')\"",
    "node -e \"require('fs').writeFileSync('/tmp/out.json','x')\"",
])
def test_allows_interpreter_writes_to_allowed_targets(proj, cmd):
    assert bash(proj, cmd).returncode == 0, cmd


@pytest.mark.parametrize("cmd", [
    "python3 -c \"open('.superlite/pool.json','w'); open('src/a.py','w').write('x')\"",
    "python3 - <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF",
])
def test_blocks_interpreter_writes_with_project_or_unknown_targets(proj, cmd):
    assert bash(proj, cmd).returncode == 2, cmd


def test_allows_nested_plans_folders(proj):
    for p in ("docs/superpowers/plans/p.progress.md", "docs/superpowers/plans/p.incidents.jsonl"):
        assert run(proj, "Write", {"file_path": p}).returncode == 0, p


def test_removing_the_state_folder_points_to_orchestrator_end(proj):
    r = bash(proj, "rm -rf .superlite")
    assert r.returncode == 2 and "sl orchestrator end" in r.stderr


# Directory targets of cp/mv/tee are judged by <dir>/<basename of the first source>.
def test_cp_into_state_dir_allowed(proj):
    assert bash(proj, "cp ../../.superlite/test-cmd.json .superlite/").returncode == 0
    assert bash(proj, "mv docs/plans/a.md .superlite/").returncode == 0


def test_mv_source_out_of_project_blocked(proj):
    assert bash(proj, "mv src/a.py .superlite/").returncode == 2


def test_cp_into_source_dir_blocked(proj):
    assert bash(proj, "cp /tmp/x.py src/").returncode == 2


def test_mv_into_existing_source_dir_blocked(proj):
    (proj / "src").mkdir()
    assert bash(proj, "mv /tmp/x.py src").returncode == 2
    assert bash(proj, "mv /tmp/x.py .superlite").returncode == 0


# sys.argv[N] resolves to the interpreter's N-th positional argument.
_ARGV_BODY = "import sys\nopen(sys.argv[1],'w').write('x')\nEOF"


def test_argv_target_through_variable_allowed(proj):
    cmd = "P=docs/plans/p.md; python3 - \"$P\" <<'EOF'\n" + _ARGV_BODY
    assert bash(proj, cmd).returncode == 0
    cmd = "P=docs/plans/p.md; python3 - \"$P\" <<'EOF'\nimport sys\np=sys.argv[1]\nopen(p,'w').write('x')\nEOF"
    assert bash(proj, cmd).returncode == 0
    assert bash(proj, "python3 - docs/plans/p.md <<'EOF'\n" + _ARGV_BODY).returncode == 0


def test_argv_target_to_source_blocked(proj):
    assert bash(proj, "python3 - src/a.py <<'EOF'\n" + _ARGV_BODY).returncode == 2
    assert bash(proj, "P=src/a.py; python3 - \"$P\" <<'EOF'\n" + _ARGV_BODY).returncode == 2
    assert bash(proj, "P=a.py; P=docs/plans/p.md; python3 - \"$P\" <<'EOF'\n" + _ARGV_BODY).returncode == 2


def test_argv_without_argument_still_blocks(proj):
    assert bash(proj, "python3 - <<'EOF'\n" + _ARGV_BODY).returncode == 2
    assert bash(proj, "python3 - docs/plans/p.md <<'EOF'\nimport sys\nopen(sys.argv[2],'w').write('x')\nEOF").returncode == 2


def test_argv_flag_with_value_does_not_shift_positions(proj):
    body = "<<'EOF'\n" + _ARGV_BODY
    assert bash(proj, "python3 -W ignore - src/a.py " + body).returncode == 2


def test_dir_target_judged_against_project_not_cwd(proj, tmp_path_factory):
    (proj / "docs" / "plans").mkdir(parents=True)
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "cp /tmp/x.md docs/plans"}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env,
                       cwd=str(tmp_path_factory.mktemp("elsewhere")))
    assert r.returncode == 0


def test_redirect_not_operand(proj):
    assert bash(proj, "cp a /tmp/b 2>/dev/null").returncode == 0


def test_real_write_stays_blocked(proj):
    assert bash(proj, "cp x src/a.py 2>/dev/null").returncode == 2


def test_escaped_quote_blocked(proj):
    assert bash(proj, 'echo "x\\"y" > src/a.py').returncode == 2


def test_multiline_quote_blocked(proj):
    assert bash(proj, 'echo "multi\nline" > src/a.py').returncode == 2


# ---- #690: the coordinator's scratch folder -------------------------------------------------------------------------

def _srun(proj, tool, tool_input, home, env_extra=None, bash_exe=None):
    env = {k: v for k, v in os.environ.items() if k != "SUPERLITE_STATE_DIR" and not k.startswith("SUPERLITE_FLEET_")}
    env.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(home), **(env_extra or {})})
    raw = json.dumps({"tool_name": tool, "tool_input": tool_input})
    return subprocess.run([bash_exe or BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


@pytest.fixture
def sproj(proj, tmp_path_factory):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("a\nb\nc\n")
    (proj / ".superlite" / "scratch").mkdir()
    home = tmp_path_factory.mktemp("slhome")

    class P:
        path = proj
        home_dir = home
        scratch = proj / ".superlite" / "scratch"

        def put(self, name, text):
            (self.scratch / name).write_text(text)

        def sh(self, cmd, **kw):
            return _srun(proj, "Bash", {"command": cmd}, home, **kw)

        def tool(self, tool, ti, **kw):
            return _srun(proj, tool, ti, home, **kw)

    return P()


BAD = "open('src/a.py','w').write('y')"


def test_scratch_write_passes(sproj):
    assert sproj.tool("Write", {"file_path": str(sproj.path / ".superlite" / "scratch" / "m.py")}).returncode == 0
    assert sproj.sh("cat > .superlite/scratch/m.py <<'EOF'\nprint(1)\nEOF").returncode == 0


def test_scratch_read_only_script_runs(sproj):
    sproj.put("m.py", "print(sum(1 for _ in open('src/a.py')))")
    sproj.put("t.sh", "wc -l src/a.py")
    assert sproj.sh("python3 .superlite/scratch/m.py").returncode == 0
    assert sproj.sh("python3 .superlite/scratch/m.py > .superlite/scratch/out.txt").returncode == 0
    assert sproj.sh("bash .superlite/scratch/t.sh").returncode == 0


@pytest.mark.parametrize("cmd", [
    "python3 .superlite/scratch/bad.py",
    "python3 {proj}/.superlite/scratch/bad.py",
    "cd src && python3 ../.superlite/scratch/bad.py",
])
def test_scratch_code_writer_blocked(sproj, cmd):
    sproj.put("bad.py", BAD)
    r = sproj.sh(cmd.format(proj=sproj.path))
    assert r.returncode == 2
    # the script writes src/a.py relative to the working directory: after `cd src` the judge resolves src/src/a.py
    assert r.stderr.rstrip("\n").splitlines()[-1] == ("Blocked target: src/src/a.py" if "cd src" in cmd else "Blocked target: src/a.py")
    assert "SL_SCRATCH_" not in r.stderr


def test_scratch_shell_code_writer_blocked(sproj):
    sproj.put("t.sh", "echo y > src/a.py")
    assert sproj.sh("bash .superlite/scratch/t.sh").returncode == 2


def test_scratch_writer_to_scratch_passes(sproj):
    sproj.put("w.py", "open('.superlite/scratch/o.txt','w').write('1')")
    assert sproj.sh("python3 .superlite/scratch/w.py").returncode == 0


def test_scratch_escaping_reaches_judge(sproj):
    head = "print(\"a\tb\", '\\\\', \"\\\"x\\\"\")\n"
    sproj.put("q.py", head + BAD + "\n")
    assert sproj.sh("python3 .superlite/scratch/q.py").returncode == 2
    sproj.put("q.py", head)
    assert sproj.sh("python3 .superlite/scratch/q.py").returncode == 0
    inc = sproj.path / ".superlite" / "incidents.jsonl"
    assert "guard-error" not in (inc.read_text() if inc.exists() else "")


def test_scratch_delimiter_line_in_body(sproj):
    sproj.put("d.py", "SL_SCRATCH_1\n" + BAD + "\n")
    assert sproj.sh("python3 .superlite/scratch/d.py").returncode == 2


def test_scratch_data_file_not_inlined(sproj):
    sproj.put("notes.txt", BAD)
    assert sproj.sh("cat .superlite/scratch/notes.txt").returncode == 0


def test_scratch_symlink_and_oversize_judged(sproj):
    sproj.put("bad.py", BAD)
    try:
        os.symlink(sproj.scratch / "bad.py", sproj.scratch / "link.py")
    except (OSError, NotImplementedError):
        pytest.skip("no symlinks")
    assert sproj.sh("python3 .superlite/scratch/link.py").returncode == 2
    sproj.put("big.py", "# x\n" * 17500 + BAD + "\n")
    r = sproj.sh("python3 .superlite/scratch/big.py")
    assert r.returncode == 2
    assert "over 65536 characters" in r.stderr


def test_scratch_large_script_is_quick(sproj):
    # ~60000 characters in ~2000 lines, each with a double quote and a backslash: the escaping must stay linear
    line = 'x = "ab\\cd"  # ' + "p" * 14
    body = (line + "\n") * 2000
    assert 55000 < len(body) < 65536
    sproj.put("big2.py", body + BAD + "\n")
    start = time.monotonic()
    r = sproj.sh("python3 .superlite/scratch/big2.py")
    assert r.returncode == 2
    assert time.monotonic() - start < 3


def test_scratch_unresolved_block_names_original_command(sproj):
    sproj.put("u.py", "import os\nopen(os.environ['OUT'], 'w').write('1')")
    r = sproj.sh("python3 .superlite/scratch/u.py")
    assert r.returncode == 2
    assert "Blocked command: python3 .superlite/scratch/u.py" in r.stderr.splitlines()
    assert "SL_SCRATCH_" not in r.stderr


def test_scratch_idle_not_judged(sproj):
    (sproj.path / ".superlite" / "pool.json").unlink()
    sproj.put("bad.py", BAD)
    assert sproj.sh("python3 .superlite/scratch/bad.py").returncode == 0


HINT_START = "- A throwaway script (count lines, compare outputs, time a command): write it under "


def _hint_before_after_run(stderr):
    lines = stderr.splitlines()
    hints = [i for i, ln in enumerate(lines) if "throwaway script" in ln]
    assert len(hints) == 1
    assert lines[hints[0] + 1].startswith("- After the run")
    assert ".superlite/scratch/" in lines[hints[0]]
    return lines


def test_scratch_hint_in_write_block(sproj):
    r = sproj.tool("Write", {"file_path": str(sproj.path / "src" / "x.py")})
    assert r.returncode == 2
    _hint_before_after_run(r.stderr)


def test_scratch_hint_in_bash_block(sproj):
    r = sproj.sh("cat > src/x.py <<'EOF'\nprint(1)\nEOF")
    assert r.returncode == 2
    lines = _hint_before_after_run(r.stderr)
    assert lines[-1] == "Blocked target: src/x.py"


def test_scratch_hint_not_in_protected_block(sproj):
    r = sproj.tool("Write", {"file_path": str(sproj.path / ".superlite" / "orchestrator.json")})
    assert r.returncode == 2
    assert "throwaway script" not in r.stderr


def test_scratch_hint_names_outside_state_dir(sproj):
    st = sproj.home_dir / "sessions" / "s1"   # a private state folder: paths are judged against the launch directory
    st.mkdir(parents=True)
    (st / "pool.json").write_text("{}")
    r = sproj.tool("Write", {"file_path": str(sproj.path / "src" / "x.py")},
                   env_extra={"SUPERLITE_STATE_DIR": str(st)})
    assert r.returncode == 2
    assert f"under {st}/scratch/ and" in r.stderr


def test_scratch_inline_quote_in_state_path(sproj):
    st = sproj.home_dir / "sessions" / "it's"   # a quote in the state folder path must survive the heredoc line
    (st / "scratch").mkdir(parents=True)
    (st / "pool.json").write_text("{}")
    (st / "scratch" / "bad.py").write_text(BAD)
    cmd = "python3 '" + str(st).replace("'", "'\\''") + "/scratch/bad.py'"
    r = sproj.sh(cmd, env_extra={"SUPERLITE_STATE_DIR": str(st)})
    assert r.returncode == 2, r.stderr
