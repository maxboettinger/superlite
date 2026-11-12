"""Guard false blocks (#554): read-only git apply, argv tuple unpack, f-string targets."""
from test_block_coordinator_edits import bash, proj  # noqa: F401


def test_git_apply_check_reads_only(proj):
    pre = "D=/tmp/x; git diff HEAD --binary > $D/b.patch; "
    assert bash(proj, pre + "git apply --check -R $D/b.patch").returncode == 0
    assert bash(proj, "git apply x.patch").returncode == 2


def test_argv_tuple_unpack(proj):
    body = "import sys\np,img=sys.argv[1],sys.argv[2]\nopen(p,'w').write('x')\nEOF"
    cmd = 'S=/tmp/sc; python3 -I - "$S/copy/A.swift" "$S/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd).returncode == 0
    cmd2 = 'python3 -I - "src/A.swift" "/tmp/sc/q.png" <<\'EOF\'\n' + body
    assert bash(proj, cmd2).returncode == 2


def test_fstring_with_unknown_piece_stays_blocked(proj):
    def code(target: str) -> str:
        return "python3 - <<'EOF'\nfrom pathlib import Path\nx='../../src/a'\n" + target + ".write_text(x)\nEOF"

    assert bash(proj, code('Path(f".superlite/plan-parts/{letter}.md")')).returncode == 2
    assert bash(proj, code('Path(f"src/{n}.py")')).returncode == 2
    assert bash(proj, code("Path(f'.superlite/plan-parts/{x}')")).returncode == 2


def test_pins_that_pass_today(proj):
    note = 'echo "Left undone: x" >> .superlite/notes.md; python3 - <<\'EOF\'\nimport json\nprint(json.load(open("docs/plans/a.json")))\nEOF'
    assert bash(proj, note).returncode == 0
    assert bash(proj, "python3 -I - <<EOF\nimport json\nprint(json.load(open('docs/plans/a.json')))\nEOF").returncode == 0


def test_fstring_glob_directly_below_superlite_root_blocks(proj):
    bad = "python3 - <<'EOF'\nimport sys\nfrom pathlib import Path\nx = sys.argv[1]\nPath(f\".superlite/{x}\").write_text('a')\nEOF"
    assert bash(proj, bad).returncode == 2
