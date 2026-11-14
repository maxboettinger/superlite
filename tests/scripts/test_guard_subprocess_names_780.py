"""#780: a subprocess program read from a list name bound once, a `*` splat of such a list, and sys.executable."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

from guard_judge import judge  # noqa: E402
from guard_tools import targets  # noqa: E402


def _py(code):
    return targets(["python3", "-c", code], text=code)


@pytest.mark.parametrize("code", [
    "import subprocess\ncmd = ['ls', '-l']\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ('git', 'status')\nsubprocess.run(cmd, capture_output=True)\n",
    "import subprocess\nbase = ['git', 'status']\nsubprocess.run([*base, '--short'])\n",
    "import subprocess\nbase = ['git', 'log']\nfor i in range(3):\n    subprocess.run([*base, '-1'])\n    subprocess.run(base)\n",
    "import subprocess\nsubprocess.run([*['git', 'log'], '-1'])\n",
    "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'print(1)'])\n",
    "import subprocess, sys\nsubprocess.run([sys.executable, '-V'], check=True)\n",
])
def test_readable_program_passes_like_a_literal_list(code):
    assert _py(code) == []


@pytest.mark.parametrize("code,want", [
    ("import subprocess\ncmd = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n", ["src/a.py"]),
    ("import subprocess\nbase = ['cp', 'x']\nsubprocess.run([*base, 'src/a.py'])\n", ["src/a.py"]),
    ("import subprocess, sys\nsubprocess.run([sys.executable, '-c', \"open('src/a.py', 'w')\"])\n", ["src/a.py"]),
])
def test_resolved_program_is_judged_by_its_words(code, want):
    assert _py(code) == want


@pytest.mark.parametrize("code", [
    "import subprocess\ncmd = ['ls']\ncmd.append('src')\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\ncmd += ['x']\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\ncmd[0] = 'rm'\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\ncmd = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess\ndef f(c):\n    c.append('x')\ncmd = ['ls']\nf(cmd)\nsubprocess.run(cmd)\n",
    "import subprocess\nfor cmd in (['ls'], ['rm', 'src/a.py']):\n    subprocess.run(cmd)\n",
    "import subprocess\nwith open('x') as cmd:\n    subprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\nif (cmd := ['rm', 'src/a.py']):\n    subprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = sys.argv[1:]\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = [sys.argv[1], 'x']\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\nglobals()['cmd'] = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess, sys\nsubprocess.run(['git', *sys.argv[1:]])\n",
    "import subprocess, sys\nsys.executable = '/bin/sh'\nsubprocess.run([sys.executable, '-c', 'rm -rf src'])\n",
    "import subprocess\nimport os as sys\nsubprocess.run([sys.executable, '-c', 'print(1)'])\n",
    "import subprocess, sys, builtins\nbuiltins.setattr(sys, 'executable', '/bin/sh')\nsubprocess.run([sys.executable, '-c', 'rm -rf src'])\n",
    "import subprocess, builtins\ncmd = ['ls']\ngetattr(builtins, 'setattr')(__import__('sys'), 'x', 1)\nsubprocess.run(cmd)\n",
    "import subprocess, __main__\ncmd = ['ls']\n__main__.cmd[:] = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = ['ls']\nsys.modules[__name__].cmd[:] = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess, inspect\ncmd = ['ls']\ninspect.currentframe().f_globals['cmd'][:] = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = ['ls']\nsys.modules['x'].f_globals['cmd'][:] = ['rm']\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = ['ls']\nx = sys.getattr\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = ['ls']\nsys.foo.cmd[:] = ['rm', 'src/a.py']\nsubprocess.run(cmd)\n",
    "import subprocess, sys\ncmd = ['ls']\nd = {'cmd': 1}\nsubprocess.run(cmd)\n",
])
def test_unreadable_program_stays_unknown(code):
    assert "?" in _py(code)


def test_scratch_script_with_a_splat_passes(tmp_path):
    p = tmp_path / "p"
    (p / ".superlite" / "scratch").mkdir(parents=True)
    cmd = ("cat > .superlite/scratch/b.py <<'EOF'\nimport subprocess\nbase = ['git', 'status']\n"
           "subprocess.run([*base, '--short'])\nEOF\npython3 .superlite/scratch/b.py")
    assert judge(cmd, str(p), str(p), "active", (str(p / ".superlite"),)) is None


@pytest.mark.parametrize("code", [
    "import subprocess, sys\nsys.__dict__['executable'] = '/bin/sh'\nsubprocess.run([sys.executable, '-c', 'rm src/a.py'])\n",
    "import subprocess, sys\nsys.__setattr__('executable', '/bin/sh')\nsubprocess.run([sys.executable, '-c', 'rm src/a.py'])\n",
])
def test_sys_executable_rewritten_through_a_dunder_stays_unknown(code):
    assert "?" in _py(code)


@pytest.mark.parametrize("code", [
    "import subprocess\ncmd = ['ls']\nmatch sys_x:\n    case [*cmd]:\n        pass\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\nmatch y:\n    case [1] as cmd:\n        pass\nsubprocess.run(cmd)\n",
    "import subprocess\ncmd = ['ls']\nmatch y:\n    case {'a': 1, **cmd}:\n        pass\nsubprocess.run(cmd)\n",
])
def test_match_bindings_make_a_list_name_unknown(code):
    assert "?" in _py(code)


@pytest.mark.parametrize("code", [
    "import subprocess\ndef run(c):\n    c.append('src')\ncmd = ['ls']\nrun(cmd)\nsubprocess.run(cmd)\n",
    "import subprocess\ndef run(c):\n    c.append('src')\ncmd = ['ls']\nrun(cmd)\n",
    "import subprocess\nsubprocess = obj\ncmd = ['ls']\nsubprocess.run(cmd)\n",
])
def test_unbound_subprocess_name_leaves_a_list_name_unknown(code):
    assert "?" in _py(code)


def test_shell_true_judges_the_first_word_as_shell_text():
    assert "src" in " ".join(_py("import subprocess\nsubprocess.run(['rm -rf src', 'x'], shell=True)\n"))
    assert "src" in " ".join(_py("import subprocess\ncmd = ['rm -rf src', 'x']\nsubprocess.run(cmd, shell=True)\n"))
    assert _py("import subprocess\nsubprocess.run(['ls -l', 'x'], shell=True)\n") == []
