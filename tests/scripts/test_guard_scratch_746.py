"""#746: a scratch script's f-string text is data; tempfile.TemporaryDirectory() is a fresh folder below the temp root."""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_tools  # noqa: E402
from guard_tools import targets  # noqa: E402
from test_block_coordinator_edits import proj, sproj  # noqa: E402,F401


@pytest.fixture
def troot(monkeypatch, tmp_path):
    r = tmp_path / "troot"
    r.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(r))
    return str(r)


def _py(code):
    return targets(["python3", "-c", code], text=code)


@pytest.mark.parametrize("code,want", [
    ('x = f"run() {y}"\n', 'x = f"' + " " * 6 + '{y}"\n'),
    ("x = f'{{a}} {b!r:>{w}}'\n", "x = f'" + " " * 6 + "{b!r:>{w}}'\n"),
    ('x = rf"run( {y}"\n', 'x = rf"' + " " * 5 + '{y}"\n'),
    ('x = f"""a\n{b}"""\n', 'x = f""" \n{b}"""\n'),
    ('x = "run()"  # open(\n', "x = " + " " * 16 + "\n"),
])
def test_mask_blanks_fstring_literal_parts(code, want):
    assert guard_tools._mask(code) == want


@pytest.mark.parametrize("code", [
    'import sys\nprint(f"run() {sys.argv[1]}")\n',
    "import sys\nprint(f\"open('src/a.py', 'w') {sys.argv[1]}\")\n",
    'import sys\nprint(f"{{run()}} {sys.argv[1]:>{10}} run()")\n',
    'print(f"""run(\n{1}""")\n',
    "print(F'run() {1}')\n",
])
def test_fstring_literal_text_is_no_call(code):
    assert _py(code) == []


def test_fstring_field_code_is_still_judged():
    assert _py("print(f\"{open('src/a.py', 'w').write('y')}\")\n") == ["src/a.py"]
    # code that can run text (subprocess) keeps every string visible, so the f-string's "run()" still reads as a call
    assert _py("import subprocess\nprint(f\"run() {1}\")\nsubprocess.run(['rm', 'src/a.py'])\n") == ["?", "src/a.py"]
    assert _py("import os\nprint(f\"run() {1}\")\nos.remove('src/a.py')\n") == ["src/a.py"]


@pytest.mark.parametrize("code", [
    "import tempfile, pathlib\nwith tempfile.TemporaryDirectory() as d:\n    (pathlib.Path(d) / 'x.txt').write_text('x')\n",
    "import tempfile, os\nwith tempfile.TemporaryDirectory(prefix='sl-', suffix='.d') as d:\n"
    "    open(os.path.join(d, 'x.txt'), 'w').write('x')\n",
    "import tempfile, os\nwith tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, open('README') as f:\n"
    "    open(os.path.join(d, 'x.txt'), 'w')\n",
    "import tempfile, os\nd = tempfile.TemporaryDirectory().name\nopen(os.path.join(d, 'x.txt'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\nopen(os.path.join(t.name, 'x.txt'), 'w')\nt.cleanup()\n",
])
def test_temporary_directory_is_a_fresh_folder_below_the_temp_root(troot, code):
    assert _py(code) == [troot + "/?/x.txt"]


@pytest.mark.parametrize("code", [
    "import tempfile, os\nwith tempfile.TemporaryDirectory(dir='src') as d:\n    open(os.path.join(d, 'a'), 'w')\n",
    "import tempfile, os\nwith tempfile.TemporaryDirectory('', '', 'src') as d:\n    open(os.path.join(d, 'a'), 'w')\n",
    "import tempfile, os\nwith tempfile.TemporaryDirectory(prefix='../x') as d:\n    open(os.path.join(d, 'a'), 'w')\n",
    "import tempfile, os\ntempfile.tempdir = 'src'\nwith tempfile.TemporaryDirectory() as d:\n    open(os.path.join(d, 'a'), 'w')\n",
    "import os\nwith open('x') as d:\n    open(os.path.join(d, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\nt.name = 'src'\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\nsetattr(t, 'name', 'src')\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\nt = 'src'\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nopen(f'{t}.txt', 'w')\n",
    "from tempfile import TemporaryDirectory\nimport os\nwith TemporaryDirectory() as d:\n    open(os.path.join(d, 'a'), 'w')\n",
])
def test_temporary_directories_the_guard_cannot_place_stay_unknown(troot, code):
    assert _py(code) == ["?"]


@pytest.mark.parametrize("code", [
    "import tempfile\nt = tempfile.TemporaryDirectory()\n(t := open('x'))\nopen(t.name + '/a', 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nt.name, y = 'src', 1\nopen(t.name + '/a', 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nfor t.name in ['src']: pass\nopen(t.name + '/a', 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nu = t\nu.name = 'src'\nopen(t.name + '/a', 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nvars(t)['name'] = 'src'\nopen(t.name + '/a', 'w')\n",
    "import tempfile\nt = tempfile.TemporaryDirectory()\nt.__dict__['name'] = 'src'\nopen(t.name + '/a', 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\n[t.name] = ['src']\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\n(t.name) = 'src'\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\nt.name: str = 'src'\nopen(os.path.join(t.name, 'a'), 'w')\n",
    "import tempfile, os\nt = tempfile.TemporaryDirectory()\ndel t.name\nopen(os.path.join(t.name, 'a'), 'w')\n",
])
def test_a_temporary_directory_object_used_in_any_other_way_stays_unknown(troot, code):
    assert _py(code) == ["?"]


def test_issue_fstring_script_runs(sproj, tmp_path_factory):
    sproj.put("x.py", 'import sys\nprint(f"run() {sys.argv[1]}")\n')
    r = sproj.sh("python3 .superlite/scratch/x.py v", env_extra={"TMPDIR": str(tmp_path_factory.mktemp("troot"))})
    assert r.returncode == 0, r.stderr


def test_issue_temporary_directory_script_runs(sproj, tmp_path_factory):
    sproj.put("t.py", 'import pathlib, tempfile\nwith tempfile.TemporaryDirectory() as d:\n'
                      '    p = pathlib.Path(d) / "x.txt"\n    p.write_text("x")\n')
    r = sproj.sh("python3 .superlite/scratch/t.py", env_extra={"TMPDIR": str(tmp_path_factory.mktemp("troot"))})
    assert r.returncode == 0, r.stderr


def test_scratch_fstring_field_writing_project_code_blocks(sproj):
    sproj.put("w.py", "print(f\"{open('src/a.py', 'w').write('y')}\")\n")
    r = sproj.sh("python3 .superlite/scratch/w.py")
    assert r.returncode == 2 and r.stderr.rstrip("\n").splitlines()[-1] == "Blocked target: src/a.py", r.stderr
