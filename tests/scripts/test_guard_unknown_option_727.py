import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401


@pytest.fixture
def code_proj(proj):  # noqa: F811
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    return proj


@pytest.mark.parametrize("cmd", [
    'sed "$F" s/a/b/ src/a.py',
    'perl "$F" -pe s/a/b/ src/a.py',
    'sed -n "$A" "$B" src/a.py',
    'cp "$F" src /tmp/n.py',
    'cp "$F" src/a.py /tmp/l.py',
    'install "$M" src/x /tmp/y',
    'rsync -a "$F" src/ /tmp/b/',
    'F=$(cat opts.txt); sed "$F" s/a/b/ src/a.py',
    "python3 - <<'EOF'\nimport subprocess, sys\np = sys.argv[1]\nsubprocess.run([\"sed\", p, \"s/a/b/\", \"src/a.py\"])\nEOF",
    "python3 -c 'import os; os.system(\"sed \\\"$F\\\" s/a/b/ src/a.py\")'",
])
def test_unknown_option_word_blocks(code_proj, cmd):  # #727
    assert bash(code_proj, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    'sed -n "${A},${B}p" src/a.py',
    'sed -n "$R" "$f"',
    "sed -n '$p' src/a.py src/b.py",
    'sed "s/$A/$B/" src/a.py',
    'sed -e "$S" src/a.py',
    'perl -ne "$X" src/a.py',
    'cp "$f" /tmp/x/',
    'cp -r "$d" .superlite/scratch/',
    'for f in $(git ls-files src); do sed -n 1,5p "$f"; done',
    'git diff --name-only | xargs sed -n 1p',
])
def test_unknown_word_that_cannot_write_passes(code_proj, cmd):  # #727
    assert bash(code_proj, cmd).returncode == 0, cmd
