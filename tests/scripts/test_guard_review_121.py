"""Coordinator guard: the fresh review of #121 (directory tracking, wrappers, stdin shells, git, archives)."""
import pytest

from test_block_coordinator_edits import bash, proj, run  # noqa: F401


@pytest.fixture
def tree(proj):
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    (proj / "docs" / "plans").mkdir(parents=True)
    return proj


def at(proj, cmd, cwd):
    return run(proj, "Bash", {"command": cmd}, cwd=str(cwd)).returncode


# Relative cd steps walk from the shell's directory; a step into a missing folder leaves the directory unknown.
def test_relative_cd_walk_starts_at_the_cwd_and_a_missing_step_voids_it(tree):
    assert at(tree, "mkdir -p t/u; cd t/u; rm ../../src/a.py", tree) == 2
    assert at(tree, "ls; cd plans; rm ../../src/a.py", tree / "docs") == 2
    # #122: a cd that starts its chain into an existing folder succeeds; one after `ls &&` may not run, so the cwd is a
    # base too: ../plans/p.md from docs/ is plans/p.md, project code
    assert at(tree, "ls; cd plans; echo x > ../plans/p.md", tree / "docs") == 0
    assert at(tree, "ls && cd plans; echo x > ../plans/p.md", tree / "docs") == 2
    assert at(tree, "ls; cd plans; echo x > ./p.md", tree / "docs") == 0


# A wrapper's --opt=value is its option, not the end of the wrapper.
@pytest.mark.parametrize("cmd", [
    "sudo --user=root -E rm src/a.py",
    "env --unset=X -i rm src/a.py",
    "timeout --kill-after=2 -s KILL 5 rm src/a.py",
    "nice --adjustment=3 -n 2 rm src/a.py",
])
def test_wrapper_long_options_with_values(tree, cmd):
    assert bash(tree, cmd).returncode == 2, cmd


# env -S splits its string into the command; sudo -s / -i with no command run a shell on stdin.
@pytest.mark.parametrize("cmd,code", [
    ("env -S 'rm src/a.py'", 2),
    ("env -S 'sed -i s/a/b/' src/a.py", 2),
    ("env --split-string='rm src/a.py'", 2),
    ("env -S 'echo hi' > /tmp/x", 0),
    ("sudo -s <<'EOF'\nrm src/a.py\nEOF", 2),
    ("sudo -i <<'EOF'\nrm src/a.py\nEOF", 2),
    ("sudo -s <<'EOF'\necho hi > /tmp/x\nEOF", 0),
])
def test_env_split_string_and_sudo_shell(tree, cmd, code):
    assert bash(tree, cmd).returncode == code, cmd


# Heredocs: an fd prefix, and several on one line, each body read in order.
@pytest.mark.parametrize("cmd,code", [
    ("bash 0<<'EOF'\nrm src/a.py\nEOF", 2),
    ("bash <<A; cat <<B >/dev/null\nrm src/a.py\nA\nB", 2),
    ("cat <<A; bash <<B\nrm src/a.py\nA\nrm src/a.py\nB", 2),
    ("cat <<A; bash <<'B'\nrm src/a.py\nA\necho hi\nB", 0),
    ("cat <<<x; bash <<'B'\nrm src/a.py\nB", 2),
    ("python3<<'EOF'\nprint(1)\nEOF", 0),
    ("cat <\"in.txt\" >/dev/null; bash <<'EOF'\nrm src/a.py\nEOF", 2),
])
def test_heredoc_forms(tree, cmd, code):
    assert bash(tree, cmd).returncode == code, cmd


# tar/unzip: a directory inside an option cluster or old-style word; extraction to stdout writes nothing.
def test_archive_clusters_and_stdout(tree, tmp_path_factory):
    out = tmp_path_factory.mktemp("elsewhere")
    for cmd in (f"tar -xzC {tree}/src -f /tmp/x.tgz", f"tar xCf {tree}/src /tmp/x.tar",
                f"unzip -od {tree}/src /tmp/x.zip", f"tar -x -C{tree}/src -f /tmp/x.tar"):
        assert at(tree, cmd, out) == 2, cmd
    for cmd in (f"tar -xzC {out} -f /tmp/x.tgz", "tar -xzf /tmp/x.tgz", f"unzip -od {out} /tmp/x.zip"):
        assert at(tree, cmd, out) == 0, cmd
    for cmd in ("tar -xOf /tmp/x.tar a.txt", "tar --to-stdout -xf /tmp/x.tar", "tar -xf /tmp/x.tar -O"):
        assert bash(tree, cmd).returncode == 0, cmd


# git: a folder operand stands for what lies in it; forced discards block in the project.
@pytest.mark.parametrize("cmd,code", [
    ("git clean -fd docs/plans", 0),
    ("git restore .superlite", 0),
    ("git rm -r docs/plans", 0),
    ("git restore docs/plans/", 0),
    ("git rm -r src", 2),
    ("git clean -fd docs", 2),
    ("git checkout -f", 2),
    ("git checkout --force main", 2),
    ("git switch --discard-changes main", 2),
    ("git switch -f main", 2),
    ("git checkout-index -a -f", 2),
    ("git checkout-index --all", 2),
    ("git read-tree -u --reset HEAD", 2),
    ("git read-tree -m -u HEAD", 2),
    ("git switch main", 0),
    ("git switch -c fix", 0),
    ("git read-tree HEAD", 0),
    ("git -C /tmp/other checkout -f", 0),
])
def test_git_folders_and_forced_forms(tree, cmd, code):
    assert bash(tree, cmd).returncode == code, cmd


# env -C / sudo -D are read off env's and sudo's own option words only, case-sensitively.
def test_directory_options_only_on_the_wrappers_own_words(tree, tmp_path_factory):
    out = tmp_path_factory.mktemp("elsewhere")
    assert at(tree, "env LC_ALL=C python3 -c \"open('out.txt','w')\"", out) == 0
    assert at(tree, "env X=1 sh -c 'echo x > notes.md'", tree / "docs") == 0
    assert at(tree, f"env -C {tree} rm src/a.py", out) == 2
    assert at(tree, f"env -u X -C {tree} rm src/a.py", out) == 2
    assert at(tree, f"sudo -D {tree} rm src/a.py", out) == 2
    assert at(tree, f"sudo --chdir={tree} rm src/a.py", out) == 2


def test_hooks_doc_names_process_substitution():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text()
    line = [x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`")][0]
    assert "process substitution" in line


# Round 2 of the review.
@pytest.mark.parametrize("cmd,code", [
    # the heredoc delimiter is the whole word; << inside $(( )) is a shift, no heredoc
    ("cat <<'EOF-1'\nx\nEOF-1\nrm src/a.py\nEOF", 2),
    ("cat <<EOF.x\nrm src/a.py\nEOF.x", 0),
    ("cat <<\\EOF\nrm src/a.py\nEOF", 0),
    ("echo $((1<<x))\nrm src/a.py\nx", 2),
    ("(( y = 1 << 2 ))\nrm src/a.py\n2", 2),
    ("echo $(( (1<<2) + 1 )) && cat <<'EOF'\nrm src/a.py\nEOF", 0),
    # here-string words: an escaped space joins, $'...' is a quoted string
    ("bash <<< rm\\ src/a.py", 2),
    ("bash <<< $'rm src/a.py'", 2),
    ("env -S $'rm src/a.py'", 2),
    ("bash -c $'rm src/a.py'", 2),
    ("eval $'rm src/a.py'", 2),
    ("bash <<< echo\\ hi", 0),
])
def test_round2_heredoc_and_string_forms(tree, cmd, code):
    assert bash(tree, cmd).returncode == code, cmd


# env and sudo options are read like getopt, each wrapper with its own value letters.
@pytest.mark.parametrize("cmd", [
    "env -iS 'rm src/a.py'",
    "sudo -Eu root rm src/a.py",
    "sudo -S rm src/a.py",
    "env -P /bin rm src/a.py",
    "sudo -u root -S -E rm src/a.py",
    "env -u X -iS 'rm src/a.py'",
])
def test_round2_wrapper_clusters(tree, cmd):
    assert bash(tree, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd,code", [
    ("git clean -fdx -e.env", 2),
    ("git restore -sv2-RELEASE src/a.py", 2),
    ("git checkout -bfix", 0),
    ("git switch -cfix", 0),
    ("git switch -Cfix origin/main", 0),
    ("git am /tmp/x.patch", 2),
    ("git -C /tmp/other am /tmp/x.patch", 0),
    ("unzip -Plazy /tmp/x.zip", 2),
    ("unzip -P lazy -l /tmp/x.zip", 0),
])
def test_round2_option_values_and_git_am(tree, cmd, code):
    assert bash(tree, cmd).returncode == code, cmd


def test_round2_git_directory_candidates_and_work_tree(tree, tmp_path_factory):
    out = tmp_path_factory.mktemp("elsewhere")
    assert at(tree, "ls; cd src; git checkout a.py", tree) == 2
    assert at(tree, f"git --git-dir={tree}/.git --work-tree={tree} -C /tmp checkout -- src/a.py", out) == 2
    assert at(tree, f"tar -xf /tmp/x.tar --cd {tree}/src", out) == 2
    assert at(tree, f"tar -xf /tmp/x.tar --cd={tree}/src", out) == 2
    assert at(tree, f"tar -xf /tmp/x.tar --cd {out}", out) == 0
