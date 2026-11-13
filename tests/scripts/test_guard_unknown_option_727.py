import sys
from pathlib import Path

import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_tools  # noqa: E402


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


@pytest.mark.parametrize("words,want", [
    (["tar", "?", "-f", "a.tar", "src/a.py"], ["?"]),  # ? may be -x
    (["tar", "-f", "a.tar", "?"], ["?"]),
    (["tar", "-xf", "a.tar", "-C", "/tmp/x", "?"], ["?"]),  # ? may be -P
    (["tar", "xf", "a.tar", "?"], ["?"]),
    (["tar", "$F", "a.tar"], ["?"]),  # the judge's word for an unread $F
    (["tar", "--extract", "-f", "a.tar", "?"], ["?"]),
    (["tar", "-czf", "/tmp/x.tgz", "?"], []),  # a literal create: one mode only
    (["tar", "-tzf", "?"], []),  # the value of -f, not an option
    (["tar", "czf", "?", "src/"], []),
    (["tar", "--create", "-f", "/tmp/x.tar", "?"], []),
    (["tar", "-cf", "x.tar", "--", "?"], []),
    (["tar", "-xOf", "a.tar", "?"], []),  # members go to stdout
    (["tar", "-f", "?", "-x"], ["./"]),
    (["tar", "-xf", "a.tar", "-C", "/tmp/x"], ["/tmp/x/"]),  # no unknown word: unchanged
])
def test_unknown_option_word_of_tar_727(words, want):
    assert guard_tools.targets(words) == want


@pytest.mark.parametrize("cmd", [
    'tar "$F" -f a.tar src/a.py',
    'tar -f a.tar "$F"',
    "python3 - <<'EOF'\nimport subprocess, sys\np = sys.argv[1]\nsubprocess.run([\"tar\", p, \"a.tar\"])\nEOF",
])
def test_unknown_tar_word_blocks(code_proj, cmd):  # #727
    assert bash(code_proj, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    'tar -czf /tmp/x.tgz "$d"',
    'tar -tzf "$A"',
    'tar czf "$OUT" src/',
    "tar -xzf a.tgz -C /tmp/x",
])
def test_tar_that_cannot_extract_an_unknown_word_passes(code_proj, cmd):  # #727
    assert bash(code_proj, cmd).returncode == 0, cmd
