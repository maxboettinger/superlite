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


def test_fstring_target_is_glob(proj):
    ok = "python3 - <<'EOF'\nfrom pathlib import Path\nx='a'\nPath(f\".superlite/plan-parts/{letter}.md\").write_text(x)\nEOF"
    bad = "python3 - <<'EOF'\nfrom pathlib import Path\nx='a'\nPath(f\"src/{n}.py\").write_text(x)\nEOF"
    assert bash(proj, ok).returncode == 0
    assert bash(proj, bad).returncode == 2


def test_pins_that_pass_today(proj):
    note = 'echo "Left undone: x" >> .superlite/notes.md; python3 - <<\'EOF\'\nimport json\nprint(json.load(open("docs/plans/a.json")))\nEOF'
    assert bash(proj, note).returncode == 0
    assert bash(proj, "python3 -I - <<EOF\nimport json\nprint(json.load(open('docs/plans/a.json')))\nEOF").returncode == 0
