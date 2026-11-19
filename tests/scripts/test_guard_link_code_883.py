"""#883: guard_tools reports code that makes a link; Path link methods name their targets."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_tools  # noqa: E402

L = ".superlite/scratch/l"


@pytest.mark.parametrize("words", [
    ["python3", "-c", f"import os; os.symlink('a.sh', '{L}')"],
    ["python3", "-c", f"import os; os.link('a.sh', '{L}')"],
    ["python3", "-c", f"from os import symlink; symlink('a.sh', '{L}')"],
    ["python3", "-c", f"from pathlib import Path; Path('{L}').symlink_to('a.sh')"],
    ["python3", "-c", f"from pathlib import Path; Path('{L}').hardlink_to('a.sh')"],
    ["python3", "-c", f"from pathlib import Path; Path('a.sh').link_to('{L}')"],
    ["python3", "-c", "import shutil; shutil.copytree('.superlite/a', '.superlite/b', symlinks=True)"],
    ["python3", "-c", f"import os; os.system('ln -s a.sh {L}')"],
    ["python3", "-c", f"import subprocess; subprocess.run(['cp', '-l', 'a.sh', '{L}'])"],
    ["python3", "-c", "import subprocess; subprocess.run(['rsync', '-a', '--link-dest=../a', 'x/', 'y/'])"],
    ["node", "-e", f"require('fs').linkSync('a.sh', '{L}')"],
    ["node", "-e", f"const fs = require('fs'); fs.symlinkSync('a.sh', '{L}')"],
    ["node", "-e", f"const fs = require('fs-extra'); fs.ensureSymlinkSync('a.sh', '{L}')"],
    ["perl", "-e", f"link 'a.sh', '{L}'"],
    ["perl", "-e", f"symlink('a.sh', '{L}')"],
    ["ruby", "-e", f"File.symlink('a.sh', '{L}')"],
    ["ruby", "-e", f"require 'fileutils'; FileUtils.ln_s('a.sh', '{L}')"],
    ["php", "-r", f"symlink('a.sh', '{L}');"],
])
def test_code_that_makes_a_link_is_reported(words):
    guard_tools.targets(words)
    assert guard_tools.makes_link() is True


@pytest.mark.parametrize("words", [
    ["python3", "-c", f"import os; os.unlink('{L}')"],
    ["python3", "-c", f"import os; print(os.readlink('{L}'), os.path.islink('{L}'))"],
    ["python3", "-c", "print('os.symlink(a, b)')"],
    ["python3", "-c", "import shutil; shutil.copytree('.superlite/a', '.superlite/b')"],
    ["python3", "-c", "import shutil; shutil.copytree('.superlite/a', '.superlite/b', symlinks=False)"],
    ["python3", "-c", "import os; os.system('cp a.sh .superlite/scratch/b.sh')"],
    ["node", "-e", f"require('fs').unlinkSync('{L}')"],
    ["perl", "-e", f"unlink '{L}'"],
    ["ls", "-l"],
])
def test_code_without_a_link_is_not_reported(words):
    guard_tools.targets(words)
    assert guard_tools.makes_link() is False


def test_flag_resets_on_the_next_call():
    guard_tools.targets(["python3", "-c", f"import os; os.symlink('a.sh', '{L}')"])
    guard_tools.targets(["python3", "-c", "print(1)"])
    assert guard_tools.makes_link() is False


@pytest.mark.parametrize("code,want", [
    ("from pathlib import Path; Path('src/a.py').symlink_to('/tmp/x')", "src/a.py"),
    ("from pathlib import Path; Path('src/a.py').hardlink_to('/tmp/x')", "src/a.py"),
    ("from pathlib import Path; Path('/tmp/x').link_to('src/a.py')", "src/a.py"),
    ("from pathlib import Path\np = Path('src/b.py')\np.symlink_to('/tmp/x')", "src/b.py"),
])
def test_path_link_methods_name_the_link(code, want):
    assert any(t.endswith(want) for t in guard_tools.targets(["python3", "-c", code], text=code))


@pytest.mark.parametrize("code", [
    "import os as o\no.symlink('a.sh', 'b')",
    "from os import symlink as s\ns('a.sh', 'b')",
    "import os\nf = os.link\nf('a.sh', 'b')",
    "import os; os.system('cp -s a.sh b')",
    "import os; os.system('cp --symbolic-link a.sh b')",
])
def test_aliased_and_symbolic_copy_link_makers_are_reported(code):
    guard_tools.targets(["python3", "-c", code])
    assert guard_tools.makes_link() is True


@pytest.mark.parametrize("code", [
    "import os; os.system('rsync -a .superlite/a/ .superlite/b/')",
    "import os; os.system('rsync -avz .superlite/a/ .superlite/b/')",
    "import os; os.system('rsync --links .superlite/a/ .superlite/b/')",
    "import os; os.system('cp -r .superlite/a .superlite/b')",
    "import os; os.system('cp -a .superlite/a .superlite/b')",
    "import os; os.system('cp -P .superlite/a/x .superlite/b/x')",
    "import os; os.system('cp --no-dereference .superlite/a/x .superlite/b/x')",
])
def test_copies_that_keep_symlinks_in_code_are_link_makers(code):
    guard_tools.targets(["python3", "-c", code])
    assert guard_tools.makes_link() is True
