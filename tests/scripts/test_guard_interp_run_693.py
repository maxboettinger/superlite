"""#693 T5: the guard judges a script file this session wrote when an interpreter or uv run runs it."""
import os
import sys

import pytest

from test_block_coordinator_edits import ROOT, bash, proj  # noqa: F401

sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))


@pytest.fixture
def out(tmp_path_factory):
    return tmp_path_factory.mktemp("out")


def put(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


PYW = "open('src/a.py','w').write('y')\n"


@pytest.mark.parametrize("form", ["python3 {o}/w.py", "python3 -u {o}/w.py", "python3 -W ignore {o}/w.py",
                                  "uv run {o}/w.py", "uv run --script {o}/w.py", "uv run python {o}/w.py",
                                  "python3 < {o}/w.py", "python3 - < {o}/w.py", "{o}/w.py"])
def test_session_interp_script_writer_blocked(proj, out, form):  # noqa: F811
    shebang = "#!/usr/bin/env python3\n" if form == "{o}/w.py" else ""
    put(out / "w.py", shebang + PYW, 0o755)
    r = bash(proj, form.format(o=out))
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


@pytest.mark.parametrize("name,body,cmd", [
    ("w.js", "require('fs').writeFileSync('src/a.js','y')\n", "node {o}/w.js"),
    ("w.rb", "File.write('src/a.rb','y')\n", "ruby {o}/w.rb")])
def test_session_other_interp_script_blocked(proj, out, name, body, cmd):  # noqa: F811
    put(out / name, body)
    r = bash(proj, cmd.format(o=out))
    assert r.returncode == 2, r.stderr


def test_session_interp_argv_target(proj, out):  # noqa: F811
    put(out / "a.py", "import sys\nopen(sys.argv[1],'w').write('y')\n")
    r = bash(proj, f"python3 {out}/a.py src/a.py")
    assert r.returncode == 2, r.stderr
    assert bash(proj, f"python3 {out}/a.py docs/plans/x.md").returncode == 0


@pytest.mark.parametrize("cmd", ["python3 -m pytest -q", "python3 -c 'print(1)'", "node -e '1'", "uv run pytest -q"])
def test_interp_code_and_module_untouched(proj, cmd):  # noqa: F811
    assert bash(proj, cmd).returncode == 0


@pytest.mark.parametrize("run_,up", [("cd .superlite/scratch && python3 m.py", "../../"), ("uv run .superlite/scratch/m.py", ""),
                                     ("cd .superlite/scratch && uv run m.py", "../../")])
@pytest.mark.parametrize("bad", [True, False])
def test_heredoc_script_matched_after_cd(proj, run_, up, bad):  # noqa: F811
    # the script's own cwd is where it runs: after the cd a project path is reached with ../../
    body = f"open('{up}src/a.py','w').write('y')\n" if bad else "print(1)\n"
    r = bash(proj, f"mkdir -p .superlite/scratch\ncat > .superlite/scratch/m.py <<'EOF'\n{body}EOF\n{run_}")
    assert r.returncode == (2 if bad else 0), r.stderr


def test_file_dunder_in_session_script(proj):  # noqa: F811
    s = proj / ".superlite" / "scratch" / "m.py"
    put(s, "from pathlib import Path\nopen(Path(__file__).parent / 'o.json','w').write('{}')\n")
    assert bash(proj, "python3 .superlite/scratch/m.py").returncode == 0
    put(s, "from pathlib import Path\nopen(Path(__file__).parent.parent.parent / 'src' / 'a.py','w').write('y')\n")
    r = bash(proj, "python3 .superlite/scratch/m.py")
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


def test_ruby_require_option_skips_its_value(proj, out):  # noqa: F811
    put(out / "w.rb", "File.write('src/a.rb','y')\n")
    r = bash(proj, f"ruby -r set {out}/w.rb")
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.rb"
    assert bash(proj, "ruby -r set -e '1'").returncode == 0


@pytest.mark.parametrize("form", ["bash -s < {o}/w.sh", "bash - < {o}/w.sh", "bash /dev/stdin < {o}/w.sh",
                                  "sh -s -- arg < {o}/w.sh"])
def test_shell_stdin_file_with_dash_forms_judged(proj, out, form):  # noqa: F811
    put(out / "w.sh", "echo y > src/a.py\n")
    r = bash(proj, form.format(o=out))
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"
    put(out / "r.sh", "wc -l src/a.py\n")
    assert bash(proj, form.format(o=out).replace("w.sh", "r.sh")).returncode == 0


@pytest.mark.parametrize("form", ["python3 -E {o}/w.py", "python3 -E -u {o}/w.py"])
def test_python_E_is_a_flag_not_code(proj, out, form):  # noqa: F811
    put(out / "w.py", PYW)
    r = bash(proj, form.format(o=out))
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


def test_perl_p_is_a_flag_not_code(proj, out):  # noqa: F811
    put(out / "w.pl", "open(F, '>src/a.pl'); print F 'y';\n")
    r = bash(proj, f"perl -p {out}/w.pl")
    assert r.returncode == 2, r.stderr
