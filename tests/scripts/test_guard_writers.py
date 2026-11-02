from test_block_coordinator_edits import bash, proj  # noqa: F401


def blocked(proj, cmds):
    for c in cmds:
        assert bash(proj, c).returncode == 2, c


def test_sed_clusters(proj):
    blocked(proj, ["sed -Ei s/a/b/ src/a.py", "sed -ni s/a/b/ src/a.py", "perl -0pi -e s/a/b/ src/a.py"])


def test_sed_every_operand(proj):
    blocked(proj, ["sed -i s/a/b/ src/a.py docs/plans/p.md", "sed -i s/a/b/ docs/plans/p.md src/a.py"])
    assert bash(proj, "sed -i s/a/b/ docs/plans/p.md").returncode == 0


def test_ruby_php_writers(proj):
    blocked(proj, ["ruby -e \"File.write('src/a.py','x')\"", "php -r \"file_put_contents('src/a.py','x');\""])


def test_open_update_mode(proj):
    blocked(proj, ["python3 -c \"open('src/a.py','r+')\""])


def test_read_open_stays_allowed(proj):
    for c in ["python3 -c \"open('src/a.py').read()\"", "python3 -c \"open('src/a.py','r')\"",
              "sed -n 1,5p src/a.py", "sed -E s/a/b/ src/a.py", "perl -ne 'print' src/a.py",
              "ruby -e \"puts File.read('src/a.py')\""]:
        assert bash(proj, c).returncode == 0, c


def test_nested_interpreter_in_shell_c(proj):
    blocked(proj, ["bash -o pipefail -c \"python3 -c \\\"open('src/a.py','w')\\\"\"",
                   "ksh -c \"python3 -c \\\"open('src/a.py','w')\\\"\""])


def test_hooks_doc_names_limit():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "hooks.md").read_text()
    line = [x for x in doc.splitlines() if x.startswith("- `block-coordinator-edits`")][0]
    assert "best-effort" in line and "one level" in line


def test_sed_script_forms_never_hide_the_file(proj):
    blocked(proj, ["sed -ie s/a/b/ src/a.py", "sed -i.bak s/a/b/ src/a.py", "sed -i '' s/a/b/ src/a.py",
                   "sed -i -e s/a/b/ src/a.py", "sed -e s/a/b/ -i src/a.py", "sed -ie -e s/a/b/ src/a.py",
                   "sed -i -es/a/b/ src/a.py", "sed -n -i -es/a/b/p src/a.py", "sed -i --expression=s/a/b/ src/a.py",
                   "sed --in-place --expression=s/a/b/ src/a.py", "sed -i --file=s.sed src/a.py",
                   "perl -i -pes/a/b/ src/a.py", "perl -pi -E s/a/b/ src/a.py"])
    for c in ["sed -i -es/a/b/ docs/plans/p.md", "sed -i --expression=s/a/b/ docs/plans/p.md",
              "sed -ie s/a/b/ docs/plans/p.md", "sed -i -e s/a/b/ -e s/c/d/ .superlite/x.md"]:
        assert bash(proj, c).returncode == 0, c
