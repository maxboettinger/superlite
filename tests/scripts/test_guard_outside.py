import json
import os
import subprocess

import pytest

from test_block_coordinator_edits import BASH, HOOK, bash, proj, run  # noqa: F401  (proj is a fixture)


@pytest.fixture
def other(tmp_path_factory):
    return tmp_path_factory.mktemp("other")


def test_cd_other_repo_relative_edit_allowed(proj, other):  # noqa: F811
    assert bash(proj, f"cd {other} && sed -i s/a/b/ src/x.py").returncode == 0
    assert bash(proj, f'cd "{other}" && sed -i s/a/b/ src/x.py').returncode == 0


def test_cd_other_repo_interpreter_allowed(proj, other):  # noqa: F811
    cmd = f"cd {other} && python3 -c \"open('src/x.py','w').write('x')\""
    assert bash(proj, cmd).returncode == 0


def test_cd_other_repo_git_apply_allowed(proj, other):  # noqa: F811
    assert bash(proj, f"cd {other} && git apply f.patch").returncode == 0
    assert bash(proj, f"cd {other} && patch -p1 < f.patch").returncode == 0
    assert bash(proj, "git apply f.patch").returncode == 2


def test_input_cwd_outside_allowed(proj, other):  # noqa: F811
    r = run(proj, "Bash", {"command": "sed -i s/a/b/ src/x.py"}, cwd=str(other))
    assert r.returncode == 0


def test_input_cwd_inside_blocked(proj):  # noqa: F811
    r = run(proj, "Bash", {"command": "sed -i s/a/b/ src/x.py"}, cwd=str(proj / "src"))
    assert r.returncode == 2


def test_cd_inside_project_blocked(proj, other):  # noqa: F811
    assert bash(proj, f"cd {proj} && sed -i s/a/b/ src/x.py").returncode == 2
    r = run(proj, "Bash", {"command": f"cd {proj} && sed -i s/a/b/ src/x.py"}, cwd=str(other))
    assert r.returncode == 2


def test_cd_back_blocked(proj, other):  # noqa: F811
    assert bash(proj, f"cd {other} && ls; cd {proj} && rm src/a.py").returncode == 2


def test_cwd_outside_then_cd_into_project_blocked(proj, other):  # noqa: F811
    for cmd in (
        f"ls; cd {proj} && rm src/a.py",
        f"cd {other} && cd {proj} && rm src/a.py",
        f"cd {other} && cd .. && rm src/a.py",
        f"pushd {proj} && rm src/a.py",
        f"cd {other} && (cd {proj} && rm src/a.py)",
        f"cd {other} && cd - && rm src/a.py",
    ):
        for extra in ({}, {"cwd": str(other)}):
            r = run(proj, "Bash", {"command": cmd}, **extra)
            assert r.returncode == 2, (cmd, extra)


def test_chdir_in_interpreter_blocked_from_outside(proj, other):  # noqa: F811
    cmd = f"cd {other} && python3 -c \"import os; os.chdir('{proj}'); open('src/a.py','w').write('x')\""
    assert bash(proj, cmd).returncode == 2


def test_dotdot_into_project_from_outside_blocked(proj, other):  # noqa: F811
    r = run(proj, "Bash", {"command": f"sed -i s/a/b/ ../{proj.name}/src/a.py"}, cwd=str(other))
    assert r.returncode == 2
    r = run(proj, "Bash", {"command": f"sed -i s/a/b/ {other}/../{proj.name}/src/a.py"})
    assert r.returncode == 2


def test_patch_and_apply_into_project_from_outside_blocked(proj, other):  # noqa: F811
    for cmd in (f"git -C {proj} apply f.patch", f"patch -d {proj} -p1 < f.patch",
                f"git apply --directory={proj} f.patch", f"patch {proj}/src/a.py < f.patch"):
        assert bash(proj, f"cd {other} && {cmd}").returncode == 2, cmd


def test_relative_cd_keeps_base(proj):  # noqa: F811
    assert bash(proj, "cd src && rm a.py").returncode == 2


def test_outside_absolute_into_project_blocked(proj, other):  # noqa: F811
    assert bash(proj, f"cd {other} && rm {proj}/src/a.py").returncode == 2


def test_protected_file_absolute_blocked_from_outside(proj, other):  # noqa: F811
    cmd = f"cd {other} && echo x > {proj}/.superlite/orchestrator.json"
    assert bash(proj, cmd).returncode == 2


def test_fstring_root_outside_allowed(proj):  # noqa: F811
    cmd = "python3 - <<'EOF'\nimport json\nopen(f\"/tmp/s/{1}.json\",'w').write('x')\nEOF"
    assert bash(proj, cmd).returncode == 0


def test_path_of_name_outside_allowed(proj):  # noqa: F811
    cmd = "python3 - <<'EOF'\nfrom pathlib import Path\np = '/tmp/s/x.json'\nPath(p).write_text('x')\nEOF"
    assert bash(proj, cmd).returncode == 0


def test_path_join_root_outside_allowed(proj):  # noqa: F811
    cmd = "python3 -c \"import os; open(os.path.join('/tmp/s','x'),'w').write('x')\""
    assert bash(proj, cmd).returncode == 0
    assert bash(proj, cmd.replace("'/tmp/s'", f"'{proj}/src'")).returncode == 2


def test_name_join_root_outside_allowed(proj):  # noqa: F811
    cmd = "uv run python - <<'EOF'\nfrom pathlib import Path\nd = Path('/tmp/s')\n(d / 'x.json').write_text('x')\nEOF"
    assert bash(proj, cmd).returncode == 0


def test_fstring_root_in_project_blocked(proj):  # noqa: F811
    assert bash(proj, "python3 -c \"open(f'{d}/a.py','w').write('x')\"").returncode == 2
    assert bash(proj, "python3 -c \"open(f\\\"src/{n}.py\\\",'w').write('x')\"").returncode == 2
    cmd = f"python3 - <<'EOF'\nd = '{proj}/src'\nopen(f\"{{d}}/a.py\",'w').write('x')\nEOF"
    assert bash(proj, cmd).returncode == 2


def test_unresolved_root_blocked(proj):  # noqa: F811
    cmd = "python3 -c \"import os; open(os.environ['X'],'w').write('x')\""
    assert bash(proj, cmd).returncode == 2


def test_relative_cd_into_project_from_ancestor_blocked(proj):  # noqa: F811
    parent = str(proj.parent)
    for cmd in (f"cd {proj.name} && rm src/a.py", f"cd {proj.name}/src && rm a.py", f"cd ./{proj.name} && rm src/a.py"):
        assert run(proj, "Bash", {"command": cmd}, cwd=parent).returncode == 2, cmd
    assert run(proj, "Bash", {"command": "cd sibling && rm a.py"}, cwd=parent).returncode == 0


@pytest.mark.parametrize("opened", ["open(Path('src/a.py'),'w')", "open(os.path.join('src','a.py'),'w')",
                                    "open('src/a.py',mode='w')", "open('src/a.py','wt')"])
def test_open_forms_with_project_target_blocked(proj, opened):  # noqa: F811
    assert bash(proj, f'python3 -c "import os; {opened}.write(1)"').returncode == 2


def test_open_reads_followed_by_mode_like_literal_allowed(proj):  # noqa: F811
    for cmd in (
        "python3 -c \"d=json.load(open('.superlite/orchestrator.json')); print(d.get('mode', 'auto'))\"",
        "python3 -c \"x=open(str(p)); y=d.get('a', 'w')\"",
        "python3 -c \"p.open(encoding='utf-8'); d.get('a', 'x')\"",
        "python3 -c \"Image.open(x)\ny=d.get('a', 'a')\"",
    ):
        assert bash(proj, cmd).returncode == 0, cmd
    assert bash(proj, "python3 -c \"open(Path('src/a.py'), 'w')\"").returncode == 2
    assert bash(proj, "python3 -c \"open(os.path.join('src','a.py'),'w')\"").returncode == 2


def test_path_join_project_target_blocked(proj):  # noqa: F811
    cmd = "python3 -c \"import os; open(os.path.join('src','x'),'w').write('x')\""
    assert bash(proj, cmd).returncode == 2
    assert bash(proj, cmd.replace("'src'", f"'{proj}/src'")).returncode == 2


def test_git_dash_c_relative_into_project_blocked(proj, other):  # noqa: F811
    cmd = f"git -C {proj.name} apply f.patch"
    assert bash(proj, f"cd {proj.parent} && {cmd}").returncode == 2
    assert run(proj, "Bash", {"command": cmd}, cwd=str(proj.parent)).returncode == 2
    assert bash(proj, f"cd {proj.parent} && git -C sibling apply f.patch").returncode == 0
    assert bash(proj, f"cd {other} && patch -d ../{proj.name} -p1 < f.patch").returncode == 2


def test_writer_root_ancestor_or_brace_blocked(proj):  # noqa: F811
    parent = str(proj.parent)
    assert bash(proj, f"python3 -c \"open(f'{parent}/{{x}}.py','w').write('x')\"").returncode == 2
    assert bash(proj, f"python3 -c \"open(f'{parent}/{{x}}','w').write('x')\"").returncode == 2
    assert bash(proj, "python3 -c \"open(f'/tmp/s/{x}.json','w').write('x')\"").returncode == 0


@pytest.mark.skipif(os.name == "nt", reason="needs symlinks")
def test_symlinked_cwd_is_the_project(proj, other):  # noqa: F811
    link = other / "link"
    link.symlink_to(proj, target_is_directory=True)
    assert run(proj, "Bash", {"command": "rm src/a.py"}, cwd=str(link)).returncode == 2
    assert run(proj, "Bash", {"command": "rm src/a.py"}, cwd=str(other)).returncode == 0


def test_git_stash_apply_and_outside_dash_c_allowed(proj, other):  # noqa: F811
    # `git stash apply` is no `git apply`; since #121 it blocks in the project as a rewrite of tracked files
    assert bash(proj, "git stash apply").returncode == 2
    assert bash(proj, f"git -C {other} stash apply").returncode == 0
    assert bash(proj, f"git -C {other} apply f.patch").returncode == 0
    assert bash(proj, f"git -c core.x=1 -C {other} apply f.patch").returncode == 0
    assert bash(proj, f"git -C {proj} apply f.patch").returncode == 2
    assert bash(proj, "git --no-pager apply f.patch").returncode == 2


def test_nested_path_division_target(proj):  # noqa: F811
    cmd = "python3 -c \"from pathlib import Path; (Path('/tmp/s') / 'a' / 'x').write_text('x')\""
    assert bash(proj, cmd).returncode == 0
    assert bash(proj, cmd.replace("'/tmp/s'", "'src'")).returncode == 2


@pytest.mark.skipif(os.name == "nt", reason="needs a shell stub for tr")
def test_no_tr_spawn_on_the_hot_path(proj, tmp_path_factory):  # noqa: F811
    fake = tmp_path_factory.mktemp("fakebin")
    marker = fake / "tr-ran"
    tr = fake / "tr"
    tr.write_text(f"#!/bin/sh\ntouch '{marker}'\ncat\n")
    tr.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "RM SRC/A.py; Python3 -c \"X\""}})
    r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and not marker.exists()
