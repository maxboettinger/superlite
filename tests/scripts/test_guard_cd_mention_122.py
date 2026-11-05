"""Coordinator guard (#122): each cd's own && chain, mkdir -p before a cd, and the protected-file mention rule."""
import re

import pytest

from test_block_coordinator_edits import ROOT, bash, proj, run  # noqa: F401

ORCH = "orchestrator.json"
NOTE = "<<'EOF'\n# note\nEOF"


@pytest.fixture
def tree(proj):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    (proj / ".superlite" / "fixes").mkdir()
    return proj


def at(proj, cmd, cwd=None):
    return run(proj, "Bash", {"command": cmd.replace("PROJ", str(proj))}, cwd=str(cwd or proj))


# Item 1a: a cd that starts a later && chain moves the commands after it in that chain.
@pytest.mark.parametrize("cmd", [
    f"echo a; cd PROJ/.superlite/fixes && cat > F.md {NOTE}",
    "echo a; cd PROJ/.superlite/fixes && echo x > F.md",
    "ls; cd .superlite/fixes && echo x > F.md",
    "echo a\ncd PROJ/.superlite/fixes && echo x > F.md",
])
def test_cd_starting_a_later_chain_judges_that_chain_from_its_target(tree, cmd):
    assert at(tree, cmd).returncode == 0, cmd


# A cd that starts its chain into an existing folder succeeds: the lines after it are judged from there.
@pytest.mark.parametrize("cmd,code", [
    ("echo a; cd PROJ/.superlite/fixes && true; echo x > F.md", 0),
    ("echo a; cd PROJ/.superlite/fixes; echo x > F.md", 0),
    ("echo a; cd PROJ/.superlite/fixes && true; echo x > ../../src/b.py", 2),
    ("echo a; cd PROJ/src; echo x > b.py", 2),
])
def test_a_sure_cd_moves_the_later_lines(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# Item 1b: `mkdir -p X && cd X` counts as reaching X, for the lines after the chain too.
@pytest.mark.parametrize("cmd", [
    f"mkdir -p .superlite/n && cd .superlite/n && cat > F1.md {NOTE}\ncat > F2.md {NOTE}",
    f"mkdir -p PROJ/.superlite/n && cd PROJ/.superlite/n && cat > F1.md {NOTE}\ncat > F2.md {NOTE}",
    "echo a; mkdir -p PROJ/.superlite/a/b && cd PROJ/.superlite/a && echo x > F.md; echo y > G.md",
    "mkdir -pv .superlite/n && cd .superlite/n; echo y > G.md",
    "mkdir --parents .superlite/n && cd .superlite/n; echo y > G.md",
])
def test_mkdir_p_then_cd_reaches_the_folder(tree, cmd):
    assert at(tree, cmd).returncode == 0, cmd


@pytest.mark.parametrize("cmd", [
    f"mkdir -p .superlite/n && cd .superlite/n && cat > F1.md {NOTE}\ncat > F2.md {NOTE}",
    "echo a; cd PROJ/.superlite/fixes && echo x > F.md",
])
def test_cwd_outside_still_passes(tree, tmp_path_factory, cmd):
    assert at(tree, cmd, tmp_path_factory.mktemp("out")).returncode == 0, cmd


# A cd that may not run, or may fail, leaves both directories possible for the lines after its chain.
@pytest.mark.parametrize("cmd", [
    "echo a; true && cd PROJ/.superlite/fixes; echo x > a.py",
    "echo a; cd PROJ/.superlite/new && echo x > F.md; echo y > a.py",
    "mkdir .superlite/n && cd .superlite/n && echo x > F.md\necho y > a.py",
    "mkdir -p .superlite/m && cd .superlite/n; echo y > a.py",
    "false && mkdir -p .superlite/n && cd .superlite/n; echo y > a.py",
    "mkdir -p .superlite/f && cd .superlite/f; echo y > a.py",
    "mkdir -p \"$X\" && cd .superlite/n; echo y > a.py",
    # control flow: the cd may not run at all
    "if false; then\ncd PROJ/.superlite/fixes\nfi\necho x > a.py",
    "for d in x; do\ncd PROJ/.superlite/fixes\ndone; echo x > a.py",
    "{ false; } && cd PROJ/.superlite/fixes; echo x > a.py",
    # a line that ends in && or \ joins the next one to its chain
    "false &&\ncd PROJ/.superlite/fixes\necho x > a.py",
    "false && \\\ncd PROJ/.superlite/fixes\necho x > a.py",
    # a cd with more words fails
    "echo a; cd PROJ/.superlite/fixes PROJ/src; echo x > a.py",
])
def test_an_uncertain_cd_never_lets_project_code_through(tree, cmd):
    (tree / ".superlite" / "f").write_text("a file, so mkdir -p fails\n")
    assert at(tree, cmd).returncode == 2, cmd


# Commands that can redefine or skip cd, or move the shell unseen, leave case D to the older, stricter judgement.
@pytest.mark.parametrize("cmd", [
    "enable -n cd; cd PROJ/.superlite/fixes; echo x > a.py",
    "shopt -s expand_aliases; alias cd=true\ncd PROJ/.superlite/fixes; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; source ./s.sh; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; . ./s.sh; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; eval \"$X\"; echo x > a.py",
])
def test_cd_redefinitions_and_unseen_moves_are_not_walked(tree, cmd):
    assert at(tree, cmd).returncode == 2, cmd


# Final review round 1: earlier commands can remove, lock or block the folder; mkdir -m; wrappers; CDPATH; comments.
@pytest.mark.parametrize("cmd", [
    "chmod 000 .superlite/fixes; cd .superlite/fixes; echo x > a.py",
    "mv .superlite/fixes /tmp/z; cd .superlite/fixes; echo x > a.py",
    "rm -rf PROJ/.superlite/fixes; cd PROJ/.superlite/fixes; echo x > a.py",
    "echo a > .superlite/n; mkdir -p .superlite/n && cd .superlite/n; echo y > a.py",
    "mkdir -p -m 000 .superlite/n && cd .superlite/n; echo y > a.py",
    "mkdir -pm 000 .superlite/n && cd .superlite/n; echo y > a.py",
    "mkdir -p --mode=000 .superlite/n && cd .superlite/n; echo y > a.py",
    "echo a; cd PROJ/.superlite/fixes; command source ./s.sh; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; builtin eval \"$X\"; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; command -p . ./s.sh; echo x > a.py",
    "trap '. ./s.sh' DEBUG; echo a; cd PROJ/.superlite/fixes; echo x > a.py",
    "export CDPATH=PROJ/src; mkdir -p docs/plans/x src/docs/plans/x && cd docs/plans/x && echo x > a.py",
    "echo a #; cd PROJ/.superlite/fixes\necho x > a.py",
])
def test_round1_a_cd_that_may_fail_or_move_elsewhere_blocks(tree, cmd):
    assert at(tree, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    "echo a; ls .superlite; cd PROJ/.superlite/fixes; echo x > F.md",
    "echo a 2>/dev/null; cd PROJ/.superlite/fixes; echo x > F.md",
])
def test_round1_read_only_commands_before_a_sure_cd_pass(tree, cmd):
    assert at(tree, cmd).returncode == 0, cmd


def test_round1_a_folder_without_search_permission_is_no_sure_cd(tree):
    nox = tree / ".superlite" / "nox"
    nox.mkdir()
    nox.chmod(0o600)
    try:
        assert at(tree, "cd PROJ/.superlite/nox; echo a; cd PROJ/.superlite/nox; echo x > a.py").returncode == 2
        assert at(tree, "echo a; mkdir -p PROJ/.superlite/nox/y && cd PROJ/.superlite/nox/y; echo x > a.py").returncode == 2
    finally:
        nox.chmod(0o700)


def test_round1_cdpath_in_the_environment_voids_relative_cds(tree):
    import json
    import os
    import subprocess

    from test_block_coordinator_edits import BASH, HOOK
    (tree / "src" / "docs" / "plans" / "x").mkdir(parents=True)
    (tree / "docs" / "plans" / "x").mkdir(parents=True)
    cmd = "echo a; cd docs/plans/x && echo x > a.py"
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(tree)})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tree), "CDPATH": f"{tree}/src"}
    assert subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env).returncode == 2
    env.pop("CDPATH")
    assert subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env).returncode == 0


def test_a_redirect_on_the_cd_is_no_extra_word(tree):
    assert at(tree, "echo a; cd PROJ/.superlite/fixes 2>/dev/null && echo x > F.md").returncode == 0


# Item 2: the mention rule judges the writer targets; scratch writers that only name the protected files pass.
def scratch_writers(out):
    return [
        f"python3 - <<'EOF'\nfrom pathlib import Path\nd = Path('{out}/.superlite'); d.mkdir(parents=True, exist_ok=True)\n"
        f"(d / '{ORCH}').write_text('{{}}')\nEOF",
        f"python3 - <<'EOF'\nopen('{out}/c.md','w').write('see .superlite/{ORCH}')\nEOF",
        f"python3 -c \"open('{out}/c.md','w').write('see .superlite/{ORCH}')\"",
        f"python3 - <<'EOF'\nt = open('.superlite/{ORCH}').read()\nopen('{out}/c.md','w').write(t)\nEOF",
        f"python3 - <<'EOF'\nt = 'see X'.replace('X', '.superlite/{ORCH}')\nopen('{out}/c.md','w').write(t)\nEOF",
    ]


def idle(tmp_path):
    (tmp_path / ".superlite").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("i", range(5))
def test_scratch_writer_naming_a_protected_file_passes_during_a_run(tree, tmp_path_factory, i):
    cmd = scratch_writers(tmp_path_factory.mktemp("out"))[i]
    assert at(tree, cmd).returncode == 0, cmd


@pytest.mark.parametrize("i", range(5))
def test_scratch_writer_naming_a_protected_file_passes_without_a_run(tmp_path, tmp_path_factory, i):
    p = idle(tmp_path)
    cmd = scratch_writers(tmp_path_factory.mktemp("out"))[i]
    assert at(p, cmd).returncode == 0, cmd


PROTECTED_WRITERS = [
    f"python3 - <<'EOF'\nopen('PROJ/.superlite/{ORCH}','w').write('{{}}')\nEOF",
    "python3 - <<'EOF'\nopen('.superlite/human-replies.jsonl','a').write('x')\nEOF",
    f"python3 -c \"from pathlib import Path; Path('.superlite/{ORCH}').write_text('x')\"",
    # an unknown target next to the name may be the protected file
    f"python3 - <<'EOF'\np = '.superlite/' + '{ORCH}'\nopen(p, 'w').write('x')\nEOF",
    f"python3 - <<'EOF'\nd = '.superlite'\nopen(f'{{d}}/{ORCH}', 'w').write('x')\nEOF",
    # round 1: a scratch write moved, copied or linked onto the protected file
    f"python3 -c \"open('/tmp/t','w').write('{{}}');import os;os.replace('/tmp/t','.superlite/{ORCH}')\"",
    f"python3 -c \"open('/tmp/t','w').write('{{}}');import shutil;shutil.copy('/tmp/t','.superlite/{ORCH}')\"",
    f"python3 -c \"from pathlib import Path;Path('/tmp/t').write_text('x');Path('/tmp/t').rename('.superlite/{ORCH}')\"",
    f"python3 -c \"from pathlib import Path;Path('/tmp/t').write_text('x');Path('/tmp/t').replace('.superlite/{ORCH}')\"",
    # last review: a read-write open on a parenthesised path, and a replace whose argument holds parentheses
    f"python3 -c \"from pathlib import Path; (Path('.superlite')/'{ORCH}').open('r+').write('{{}}')\"",
    f"python3 -c \"from pathlib import Path; (Path('.superlite')/'{ORCH}').open(mode='rb+').write(b'x')\"",
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(Path('.superlite/{ORCH}'))\"",
    f"python3 -c \"from pathlib import Path; p=Path('.superlite/{ORCH}'); Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(str(p))\"",
]


def human(tmp_path):
    (tmp_path / ".superlite").mkdir(parents=True)
    (tmp_path / ".superlite" / ORCH).write_text('{"mode": "human", "approved": false}')
    return tmp_path


@pytest.mark.parametrize("cmd", PROTECTED_WRITERS)
def test_protected_or_unknown_writer_target_blocks_in_every_state(tree, tmp_path_factory, cmd):
    for p in (tree, idle(tmp_path_factory.mktemp("idle")), human(tmp_path_factory.mktemp("human"))):
        r = at(p, cmd)
        assert r.returncode == 2, (p, cmd)
        assert "never written directly" in r.stderr, (p, cmd)


def test_a_read_write_open_on_a_parenthesised_path_blocks_during_a_run(tree):
    assert at(tree, "python3 -c \"from pathlib import Path; (Path('src')/'a.py').open('r+').write('x')\"").returncode == 2


# Last review: a command word glued to a redirect is still the command word; pushd leaves case D.
@pytest.mark.parametrize("cmd", [
    "rmdir>/dev/null test .superlite/fixes; cd .superlite/fixes; echo x > a.py",
    "rmdir</dev/null true .superlite/fixes; cd .superlite/fixes; echo x > a.py",
    "echo a; cd PROJ/.superlite/fixes; pushd ../../src; echo x > a.py",
])
def test_last_review_glued_redirects_and_pushd_block(tree, cmd):
    assert at(tree, cmd).returncode == 2, cmd


def test_a_project_writer_naming_the_file_passes_only_without_a_run(tree, tmp_path_factory):
    cmd = f"python3 -c \"open('src/a.py','w').write('{ORCH}')\""
    assert at(idle(tmp_path_factory.mktemp("idle")), cmd).returncode == 0
    r = at(tree, cmd)
    assert r.returncode == 2 and "must not write project code" in r.stderr


# Item 3: the docs say where the guard takes the shell's directory from.
def test_hooks_doc_cites_the_cwd_source_and_the_new_rules():
    doc = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    line = next(x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`"))
    for needle in ("the new directory after Claude runs `cd`", "`mkdir -p X && cd X`", "names a protected file",
                   "a move, copy or link API next to it"):   # #124 dropped the writer-call condition
        assert needle in line, needle
    assert re.search(r"own `&&` chain", line)
