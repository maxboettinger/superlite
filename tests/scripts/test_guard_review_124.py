"""Coordinator guard (#124): findings from #121's last review and the #134 follow-ups, one regression test each."""
import pytest

from test_block_coordinator_edits import ROOT, bash, proj, run  # noqa: F401

ORCH = "orchestrator.json"


@pytest.fixture
def tree(proj):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    (proj / ".superlite" / "fixes").mkdir()
    (proj / "docs" / "plans").mkdir(parents=True)
    return proj


def at(proj, cmd, cwd=None):
    return run(proj, "Bash", {"command": cmd.replace("PROJ", str(proj))}, cwd=str(cwd or proj))


def idle(tmp_path):
    (tmp_path / ".superlite").mkdir(parents=True)
    return tmp_path


def human(tmp_path):
    (tmp_path / ".superlite").mkdir(parents=True)
    (tmp_path / ".superlite" / ORCH).write_text('{"mode": "human", "approved": false}')
    return tmp_path


def states(tree, factory):
    return (tree, idle(factory.mktemp("idle")), human(factory.mktemp("human")))


# Item 13: next to a protected name every .replace( blocks unless it reads as str.replace (quoted first argument, comma).
@pytest.mark.parametrize("cmd", [
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(str(Path('.superlite/{ORCH}')))\"",
    f"python3 -c \"import os; from pathlib import Path; d='.superlite'; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(Path(os.path.join(d, '{ORCH}')))\"",
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(t := '.superlite/{ORCH}')\"",
    f"python3 -c \"from pathlib import Path; p='.superlite/{ORCH}'; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace(p)\"",
    # a trailing comma is no second argument
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text('x'); Path('/tmp/s').replace('.superlite/{ORCH}', )\"",
])
def test_item13_replace_onto_a_protected_file_blocks_in_every_state(tree, tmp_path_factory, cmd):
    for p in states(tree, tmp_path_factory):
        r = at(p, cmd)
        assert r.returncode == 2, (p, cmd)
        assert "never written directly" in r.stderr, (p, cmd)


@pytest.mark.parametrize("cmd", [
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text(open('.superlite/{ORCH}').read().replace('a', 'b'))\"",
    f"python3 -c \"from pathlib import Path; Path('/tmp/s').write_text(open('.superlite/{ORCH}').read().replace(\\\"a\\\" , 'b'))\"",
])
def test_item13_str_replace_next_to_the_name_passes(tree, tmp_path_factory, cmd):
    for p in states(tree, tmp_path_factory):
        assert at(p, cmd).returncode == 0, (p, cmd)


# Item 12: redirect words after `--` are no git paths.
@pytest.mark.parametrize("cmd,code", [
    ("git checkout -- docs/plans/p.md 2>/dev/null", 0),
    ("git checkout -- docs/plans/p.md 2> /dev/null", 0),
    ("git restore -- docs/plans/p.md >/dev/null 2>&1", 0),
    ("git checkout -- src/a.py 2>/dev/null", 2),
    ("git checkout -- docs/plans/p.md > src/b.py", 2),
])
def test_item12_redirects_after_double_dash_are_not_paths(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# Item 1: a heredoc ends only on its exact delimiter line (`<<-` strips leading tabs only).
RM = "r" + "m"


@pytest.mark.parametrize("cmd,code", [
    (f"cat <<A\n A\ncat <<B\nA\n{RM} src/a.py\nB", 2),
    (f"cat <<A\nA \ncat <<B\nA\n{RM} src/a.py\nB", 2),
    (f"cat <<-A\n  A\ncat <<B\nA\n{RM} src/a.py\nB", 2),
    (f"x=\"$(cat <<'A'\n A\ncat <<B\nA\n)\"\n{RM} src/a.py\nB", 2),
    ("cat <<-A > docs/plans/a.md\n\tbody\n\tA\necho x > docs/plans/b.md", 0),
    (f"cat <<-A > docs/plans/a.md\n\tA\ncat <<B > docs/plans/b.md\n{RM} src/a.py\nB", 0),
    ("cat <<A > docs/plans/a.md\nbody\nA\necho x > docs/plans/b.md", 0),
])
def test_item1_heredoc_ends_only_on_its_exact_delimiter(tree, cmd, code):
    assert at(tree, cmd).returncode == code, repr(cmd)


# Item 2: a << inside a comment starts no heredoc; a # inside a word starts no comment.
@pytest.mark.parametrize("cmd,code", [
    (f"echo hi # <<B\n{RM} src/a.py\nB", 2),
    (f"echo hi;# <<B\n{RM} src/a.py\nB", 2),
    (f"# <<B\n{RM} src/a.py\nB", 2),
    (f"echo hi # x \"$(cat <<'B'\n{RM} src/a.py\nB", 2),
    (f"echo a#b <<B > docs/plans/a.md\n{RM} src/a.py\nB", 0),
    (f"echo ${{#x}} <<B > docs/plans/a.md\n{RM} src/a.py\nB", 0),
    (f"echo 'a'#b <<B > docs/plans/a.md\n{RM} src/a.py\nB", 0),
])
def test_item2_a_heredoc_in_a_comment_is_no_heredoc(tree, cmd, code):
    assert at(tree, cmd).returncode == code, repr(cmd)


# Item 3: tar joins a relative -C onto the one before it; members may go to every -C, so each one is judged.
@pytest.mark.parametrize("cmd,code", [
    ("tar -xf /tmp/x.tar -C PROJ -C src", 2),
    ("tar -x -f /tmp/x.tar -CPROJ -Csrc", 2),
    ("tar --directory=PROJ --directory=src -xf /tmp/x.tar", 2),
    ("tar xCf PROJ /tmp/x.tar -C src", 2),
    ("tar -xf /tmp/x.tar -C PROJ/src a.py -C /tmp b", 2),
    ("tar -xf /tmp/x.tar -C PROJ -C .superlite", 0),
    ("tar -xf /tmp/x.tar -C /tmp -C PROJ/docs/plans", 0),
    ("tar -xf /tmp/x.tar -C PROJ/src -C /tmp", 0),
    ("tar -xf /tmp/x.tar a.py -C /tmp", 0),
])
def test_item3_tar_joins_relative_dirs_and_judges_each(tree, tmp_path_factory, cmd, code):
    assert at(tree, cmd, tmp_path_factory.mktemp("out")).returncode == code, cmd


# Item 4: tar takes a long option shortened to a prefix; an unclear prefix counts as the riskier option.
@pytest.mark.parametrize("cmd,out,code", [
    ("tar --ext -f /tmp/x.tar", 0, 2),
    ("tar --extr -f /tmp/x.tar", 0, 2),
    ("tar --ge -f /tmp/x.tar", 0, 2),
    ("tar -xf /tmp/x.tar --dir=PROJ/src", 1, 2),
    ("tar -xf /tmp/x.tar --dire PROJ/src", 1, 2),
    ("tar -xf /tmp/x.tar --to", 0, 2),
    ("tar -xf /tmp/x.tar --abs -C /tmp", 0, 2),
    ("tar -xf /tmp/x.tar --to-s", 0, 0),
    ("tar -tf /tmp/x.tar --dir=PROJ/src", 0, 0),
    ("tar -xf /tmp/x.tar --dir=/tmp", 0, 0),
])
def test_item4_tar_long_option_prefixes(tree, tmp_path_factory, cmd, out, code):
    cwd = tmp_path_factory.mktemp("out") if out else None
    assert at(tree, cmd, cwd).returncode == code, cmd


# Item 5: git takes a long option shortened to a unique prefix.
@pytest.mark.parametrize("cmd,code", [
    ("git reset --har", 2),
    ("git reset --m HEAD~1", 2),
    ("git reset --kee", 2),
    ("git checkout --forc", 2),
    ("git switch --discard main", 2),
    ("git switch --forc main", 2),
    ("git checkout-index --al", 2),
    ("git checkout --pathspec-fr=/tmp/l", 2),
    ("git restore --stag --work src/a.py", 2),
    ("git reset --mixed", 0),
    ("git reset --mi HEAD~1", 0),
    ("git rm --cac src/a.py", 0),
    ("git clean --dry", 0),
    ("git restore --stag src/a.py", 0),
])
def test_item5_git_long_option_prefixes(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# Item 6: GIT_WORK_TREE and core.worktree name the work tree like --work-tree; a -c alias is judged as what it runs.
@pytest.mark.parametrize("cmd,out,code", [
    ("GIT_DIR=PROJ/.git GIT_WORK_TREE=PROJ git checkout -- src/a.py", 1, 2),
    ("env GIT_WORK_TREE=PROJ git checkout -- src/a.py", 1, 2),
    ("GIT_WORK_TREE='PROJ' git checkout -- src/a.py", 1, 2),
    ("export GIT_WORK_TREE=PROJ; git checkout -- src/a.py", 1, 2),
    ("git -C \"$X\" checkout -- src/a.py", 1, 2),
    ("git --git-dir=PROJ/.git -c core.worktree=PROJ checkout -- src/a.py", 1, 2),
    ("GIT_WORK_TREE=/tmp/x git checkout -- src/a.py", 1, 0),
    ("GIT_WORK_TREE=PROJ git --work-tree=/tmp/x checkout -- src/a.py", 1, 0),
    (f"git -c 'alias.x=!{RM} src/a.py' x", 0, 2),
    (f"git -c 'alias.x=!{RM}' x src/a.py", 0, 2),
    ("git -c alias.co=checkout co -- src/a.py", 0, 2),
    ("git -c alias.x='checkout -f' x", 0, 2),
    ("git --config-env=alias.x=CMD x", 0, 2),
    ("git -c include.path=/tmp/cfg x", 0, 2),
    (f"GIT_CONFIG_PARAMETERS=\"'alias.x=!{RM} src/a.py'\" git x", 0, 2),
    ("git -c alias.st=status st", 0, 0),
    ("git -c 'alias.x=!echo hi > docs/plans/a.md' x", 0, 0),
    ("git -c user.name=x checkout -- docs/plans/p.md", 0, 0),
])
def test_item6_git_work_tree_env_and_aliases(tree, tmp_path_factory, cmd, out, code):
    cwd = tmp_path_factory.mktemp("out") if out else None
    assert at(tree, cmd, cwd).returncode == code, cmd


def test_item6_an_alias_writing_a_protected_file_blocks_without_a_run(tmp_path):
    r = at(idle(tmp_path), f"git -c 'alias.x=!echo x > .superlite/{ORCH}' x")
    assert r.returncode == 2 and "never written directly" in r.stderr


# Item 7: a -c or eval body that reads stdin as its program runs the segment's heredocs and here-strings.
@pytest.mark.parametrize("cmd,code", [
    (f"bash -c \"$(cat)\" <<'EOF'\n{RM} src/a.py\nEOF", 2),
    (f"eval \"$(cat)\" <<'EOF'\n{RM} src/a.py\nEOF", 2),
    (f"eval `cat` <<'EOF'\n{RM} src/a.py\nEOF", 2),
    (f"bash -c \"$(cat)\" <<<'{RM} src/a.py'", 2),
    (f"bash -c 'source /dev/stdin' <<'EOF'\n{RM} src/a.py\nEOF", 2),
    (f"bash -c 'bash' <<<'{RM} src/a.py'", 2),
    (f"sh -c 'eval \"$(cat)\"' <<'EOF'\n{RM} src/a.py\nEOF", 2),
    (f"bash -c 'cat > docs/plans/a.md' <<'EOF'\n{RM} src/a.py\nEOF", 0),
    ("bash -c \"$(cat)\" <<'EOF'\necho x > docs/plans/a.md\nEOF", 0),
])
def test_item7_a_body_reading_stdin_runs_the_heredoc(tree, cmd, code):
    assert at(tree, cmd).returncode == code, repr(cmd)


# Item 8: an unquoted -c word is read like the shell reads it: escaped spaces join words, escapes are undone.
@pytest.mark.parametrize("cmd,code", [
    (f"bash -c {RM}\\ src/a.py", 2),
    (f"sh -ec {RM}\\ \\src/a.py", 2),
    (f"bash -c {RM}\\ 'src/a.py'", 2),
    (f"bash -c echo\\ x\\ >\\ docs/plans/a.md", 0),
    (f"bash -c {RM} src/a.py", 0),
])
def test_item8_an_unquoted_c_word_is_decoded(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# Item 9: a command word glued to a redirect, after a leading redirect, or spelled with escapes is still the command.
@pytest.mark.parametrize("cmd,code", [
    (f"bash<<<'{RM} src/a.py'", 2),
    (f"bash<<<\"{RM} src/a.py\"", 2),
    (f"<<<'{RM} src/a.py' bash", 2),
    (f"{RM}>/dev/null src/a.py", 2),
    (f"/bin/{RM}>/dev/null src/a.py", 2),
    (f"{RM}&>/dev/null src/a.py", 2),
    (f"{RM}2>/dev/null src/a.py", 0),
    (f">/dev/null {RM} src/a.py", 2),
    (f"2>/dev/null {RM} src/a.py", 2),
    (f"> /tmp/o {RM} src/a.py", 2),
    (f"\\{RM} src/a.py", 2),
    (f"r\\m src/a.py", 2),
    (f"\\env {RM} src/a.py", 2),
    (f"env >/dev/null {RM} src/a.py", 2),
    ("\\git checkout -- src/a.py", 2),
    ("sed>/dev/null -i s/x/y/ src/a.py", 2),
    (f"{RM}>/dev/null docs/plans/a.md", 0),
    ("\\echo x > docs/plans/a.md", 0),
    ("echo x>docs/plans/a.md", 0),
    ("cat<docs/plans/p.md", 0),
    ("bash<<<'echo x > docs/plans/a.md'", 0),
])
def test_item9_the_command_word_is_read_past_redirects_and_escapes(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# Item 10: a relative path is judged from every directory the relative cd steps visit, too; while the directory is
# unknown, a relative path that passes only by its allowed prefix (docs/plans/...) blocks (Max: "Block them").
@pytest.mark.parametrize("cmd,code", [
    ("ls; cd src; mkdir -p docs/plans; echo x > docs/plans/a.py", 2),
    ("ls | cat; cd src; mkdir -p docs/plans; echo x > docs/plans/a.py", 2),
    ("ls | cat; cd src; echo x > docs/plans/a.md", 2),
    ("ls | cat; cd src; echo x > docs/plans/a.md; cd sub; ls", 2),
    ("ls | cat; cd nope; echo x > docs/plans/a.md", 2),
    ("ls | cat; cd nope; echo x > ./docs/plans/a.md", 2),
    ("ls | cat; cd nope; echo x > .superlite/fixes/a.md", 2),
    ("bash -c 'cd /tmp; echo x > docs/plans/a.md'", 2),
    ("ls | cat; cd nope; echo x > SPEC.md", 0),
    ("ls | cat; cd nope; echo x > PROJ/docs/plans/a.md", 0),
    ("ls | cat; echo x > docs/plans/a.md", 0),
    ("ls | cat; cd src; echo x > SPEC.md", 0),
])
def test_item10_relative_paths_follow_the_cd_steps(tree, cmd, code):
    (tree / "src" / "sub").mkdir()
    assert at(tree, cmd).returncode == code, cmd


def test_item10_an_unknown_directory_changes_nothing_without_a_run(tmp_path):
    assert at(idle(tmp_path), "ls | cat; cd nope; echo x > docs/plans/a.md").returncode == 0


# Item 11: a cd the cd block cannot read (c''d, "cd", c\d, a hidden pushd) leaves the directory unknown from there on.
@pytest.mark.parametrize("cmd,out,code", [
    (f"c''d PROJ/src; {RM} a.py", 1, 2),
    (f"\"cd\" PROJ/src; {RM} a.py", 1, 2),
    (f"c\\d PROJ/src; {RM} a.py", 1, 2),
    (f"pu''shd PROJ/src; {RM} a.py", 1, 2),
    (f"bash -c \"c''d PROJ/src; {RM} a.py\"", 1, 2),
    (f"cd PROJ/docs/plans && c''d PROJ/src && {RM} docs/plans/a.py", 0, 2),
    (f"cd PROJ/docs/plans && ls; c''d PROJ/src; {RM} a.py", 0, 2),
    (f"cd PROJ/docs/plans && ls; c''d PROJ/src; cd PROJ/docs/plans; {RM} a.md", 0, 2),
    ("c''d /tmp; ls", 1, 0),
    ("c''d PROJ/src; echo x > /tmp/o", 1, 0),
    ("cd PROJ/docs/plans && ls; echo x > a.md", 0, 0),
])
def test_item11_a_cd_the_cd_block_cannot_read_voids_the_base(tree, tmp_path_factory, cmd, out, code):
    cwd = tmp_path_factory.mktemp("out") if out else None
    assert at(tree, cmd, cwd).returncode == code, cmd


# Item 14: case B (one && chain, or one leading cd) is no sure walk when a command may move the shell unseen (source, .,
# eval, alias, enable, trap; also after VAR=, builtin, command, time), when the leading cd's folder cannot be entered, or
# when CDPATH may send a relative cd elsewhere. A leading cd into the project is then still judged as a directory.
@pytest.mark.parametrize("cmd,code", [
    ("cd PROJ/.superlite/fixes; source ./s.sh; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; . ./s.sh; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; eval \"$X\"; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes && source ./s.sh && echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; X=1 source ./s.sh; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; time source ./s.sh; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; builtin source ./s.sh; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; alias ls=x; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; 2>/dev/null eval \"$X\"; echo x > a.py", 2),
    ("echo a; cd PROJ/.superlite/fixes; X=1 source ./s.sh; echo x > a.py", 2),
    ("echo a; cd PROJ/.superlite/fixes; time eval \"$X\"; echo x > a.py", 2),
    ("cd PROJ/src; source ./s.sh; echo x > docs/plans/a.md", 2),
    ("cd PROJ/.superlite/fixes; if true; then source ./s.sh; fi; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; for i in 1; do eval \"$X\"; done; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; { . ./s.sh; }; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; function f { source ./s.sh; }; f; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; case x in x) source ./s.sh;; esac; echo x > a.py", 2),
    ("cd PROJ/.superlite/fixes; if true; then echo a; fi; echo x > a.py", 0),
    ("cd PROJ/.superlite/fixes; echo x > a.py", 0),
    ("cd PROJ/.superlite/fixes && echo x > a.md", 0),
    ("cd PROJ/.superlite/fixes; ls .; echo x > a.py", 0),
    ("cd PROJ; source .venv/bin/activate; echo x > .superlite/out.json", 0),
])
def test_item14_case_b_needs_a_shell_nothing_moves_unseen(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


def test_item14_a_leading_cd_into_a_folder_without_search_permission_is_no_walk(tree, tmp_path_factory):
    nox = tree / ".superlite" / "nox"
    onx = tmp_path_factory.mktemp("onx")
    nox.mkdir()
    for d in (nox, onx):
        d.chmod(0o600)
    try:
        assert at(tree, "cd PROJ/.superlite/nox; echo x > a.py").returncode == 2
        assert at(tree, f"cd {onx}; {RM} a.py").returncode == 2
    finally:
        for d in (nox, onx):
            d.chmod(0o700)


@pytest.mark.parametrize("cmd,code", [
    ("cd fixes; echo x > a.py", 2),
    ("cd fixes; echo x > ./a.py", 2),
    ("cd fixes && echo x > a.py", 2),
    ("cd ./fixes; echo x > a.py", 0),
    ("cd PROJ/.superlite/fixes; echo x > a.py", 0),
])
def test_item14_cdpath_may_send_a_relative_cd_elsewhere(tree, monkeypatch, cmd, code):
    (tree / "src" / "fixes").mkdir()
    monkeypatch.setenv("CDPATH", str(tree / "src"))
    assert at(tree, cmd, tree / ".superlite").returncode == code, cmd


def test_item14_cdpath_set_in_the_command_voids_relative_cds(tree):
    (tree / "src" / "fixes").mkdir()
    assert at(tree, "CDPATH=PROJ/src; cd fixes; echo x > ./a.py", tree / ".superlite").returncode == 2


# Item 15: next to a protected file's name, a move, copy or link API blocks in every state, with no writer call too.
@pytest.mark.parametrize("cmd", [
    f"python3 -c \"import shutil; shutil.copy('/tmp/p', '.superlite/{ORCH}')\"",
    f"python3 -c \"import os; os.replace('/tmp/p', '.superlite/{ORCH}')\"",
    f"python3 -c \"from pathlib import Path; Path('/tmp/p').rename('.superlite/{ORCH}')\"",
    f"node -e \"require('fs').copyFileSync('/tmp/p', '.superlite/{ORCH}')\"",
    "python3 -c \"import os; os.symlink('/tmp/p', '.superlite/human-replies.jsonl')\"",
    f"bash -c \"python3 -c 'import shutil; shutil.move(\\\"/tmp/p\\\", \\\".superlite/{ORCH}\\\")'\"",
])
def test_item15_a_move_api_next_to_a_protected_name_blocks_without_a_writer(tree, tmp_path_factory, cmd):
    for p in states(tree, tmp_path_factory):
        r = at(p, cmd)
        assert r.returncode == 2, (p, cmd)
        assert "never written directly" in r.stderr, (p, cmd)


@pytest.mark.parametrize("cmd", [
    f"python3 -c \"import json; print(json.load(open('.superlite/{ORCH}')))\"",
    f"echo \"shutil.copy('/tmp/p', '.superlite/{ORCH}')\"",
    "python3 -c \"import shutil; shutil.copy('/tmp/p', '/tmp/q')\"",
])
def test_item15_reads_and_quoted_text_pass(tree, tmp_path_factory, cmd):
    for p in states(tree, tmp_path_factory):
        assert at(p, cmd).returncode == 0, (p, cmd)


# Review round 1 (#124).
# R1-1: a git operand glued to a redirect keeps the text before it (main blocked these; regression).
@pytest.mark.parametrize("cmd,code", [
    ("git checkout -- src/a.py>/dev/null", 2),
    ("git restore -- src/a.py>/dev/null", 2),
    ("git rm -- src/a.py2>/dev/null", 2),
    ("git checkout HEAD src/a.py>/dev/null", 2),
    ("git checkout -- docs/plans/p.md>/dev/null", 0),
    ("git checkout -- docs/plans/p.md 2>/dev/null", 0),
])
def test_r1_git_operand_glued_to_a_redirect(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd


# R1-2: an alias that runs another -c alias blocks (one level deep); a ! alias runs at the work tree's top.
@pytest.mark.parametrize("cmd,cwd,code", [
    (f"git -c alias.a=b -c 'alias.b=!{RM} src/a.py' a", "", 2),
    ("git -c alias.a=b -c alias.b=status a", "", 2),
    ("git -c 'alias.w=!printf x > src/a.py' w", "docs/plans", 2),
    ("git -c 'alias.w=!printf x > docs/plans/a.md' w", "docs/plans", 0),
])
def test_r1_git_alias_chains_and_shell_alias_directory(tree, cmd, cwd, code):
    assert at(tree, cmd, tree / cwd if cwd else None).returncode == code, cmd


# R1-3: a git config written, or a git dir named, in the command is a config the guard cannot read.
@pytest.mark.parametrize("cmd,out,code", [
    (f"git config alias.w '!{RM} src/a.py' && git w", 0, 2),
    ("git --git-dir=PROJ/.git config core.worktree PROJ && git --git-dir=PROJ/.git checkout HEAD -- src/a.py", 1, 2),
    ("GIT_DIR=PROJ/.git git x", 0, 2),
    ("git config user.name x && git status", 0, 0),
    ("git --git-dir=PROJ/.git log", 1, 0),
])
def test_r1_git_config_in_the_command_is_unknown(tree, tmp_path_factory, cmd, out, code):
    cwd = tmp_path_factory.mktemp("out") if out else None
    assert at(tree, cmd, cwd).returncode == code, cmd


# R1-4: while the directory is unknown, a relative path ending in a protected name is protected; an unreadable git
# directory, and a stdin body after a cd, judge from the root with the directory unknown.
def test_r1_unknown_dir_and_a_protected_name(tmp_path):
    p = idle(tmp_path)
    for cmd in (f"c''d .superlite; printf '{{}}' > {ORCH}", "ls | cat; cd nope; printf x > human-replies.jsonl"):
        r = at(p, cmd)
        assert r.returncode == 2 and "never written directly" in r.stderr, cmd
    assert at(p, "c''d .superlite; printf x > notes.md").returncode == 0


@pytest.mark.parametrize("cmd,code", [
    ("git -C \"$X\" checkout HEAD -- docs/plans/p.md", 2),
    ("cd src; bash -c \"$(cat)\" <<'EOF'\necho x > docs/plans/a.md\nEOF", 2),
    ("git -C \"$X\" checkout HEAD -- SPEC.md", 0),
])
def test_r1_unknown_git_dir_and_stdin_body_judge_with_the_dir_unknown(tree, cmd, code):
    assert at(tree, cmd).returncode == code, repr(cmd)


# Last review (#124): a tar option's value is no member name, so it sends no extraction to the shell's directory.
@pytest.mark.parametrize("cmd,code", [
    ("tar -x --file /tmp/x.tar -C /tmp", 0),
    ("tar -x --fil /tmp/x.tar -C /tmp", 0),
    ("tar -xf /tmp/x.tar --strip-components 1 -C /tmp", 0),
    ("tar -x -I zstd -f /tmp/x.tar -C /tmp", 0),
    ("tar -x --use-compress-program zstd -f /tmp/x.tar -C /tmp", 0),
    ("tar -x --exclude a.py -f /tmp/x.tar -C /tmp", 0),
    ("tar -x --file /tmp/x.tar a.py -C /tmp", 2),
    ("tar -x --strip-components 1 -f /tmp/x.tar", 2),
    ("tar -x --exclude a.py -f /tmp/x.tar", 2),
])
def test_last_tar_option_values_are_no_members(tree, cmd, code):
    assert at(tree, cmd).returncode == code, cmd
