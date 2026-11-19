import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_tools  # noqa: E402


def py(code):
    return guard_tools.targets(["python3", "-c", code])


def test_walrus_joins_values():
    assert "src/a.py" in py('s = "docs/x"\n(s := "src")\nopen(s + "/a.py", "w")')
    assert "?" in py('s = "docs/x"\nif (s := input()):\n    pass\nopen(s + "/a.py", "w")')
    assert "?" in py('s = "docs/x"\nys = [y for y in range(3) if (s := input())]\nopen(s + "/a.py", "w")')
    assert "?" in py('s = "docs/x"\nprint((s := input()))\nopen(s + "/a.py", "w")')


def test_two_literal_bindings_union_and_third_unknown():
    out = py('s = "docs/x"\n(s := "src")\nopen(s + "/a.py", "w")')
    assert {"docs/x/a.py", "src/a.py"} <= set(out)
    assert "?" in py('s = "docs/x"\n(s := "src")\ns = input()\nopen(s + "/a.py", "w")')


@pytest.mark.parametrize("code", [
    'import __main__\ns = "docs/x"\n__main__.s = "src"\nopen(s + "/a.py", "w")',
    'import sys\ns = "docs/x"\nsys.modules[__name__].s = "src"\nopen(s + "/a.py", "w")',
    's = "docs/x"\nglobals()["s"] = "src"\nopen(s + "/a.py", "w")',
    'import sys\ns = "docs/x"\nsetattr(sys.modules[__name__], "s", "src")\nopen(s + "/a.py", "w")',
    's = "docs/x"\nfrom cfg import s\nopen(s + "/a.py", "w")',
    's = "docs/x"\nimport cfg as s\nopen(s + "/a.py", "w")',
])
def test_rebinding_makes_name_unknown(code):
    assert "?" in py(code)


def test_unrelated_rebinding_keeps_value():
    assert py('class C: pass\nc = C()\nc.t = "src"\ns = "docs/x"\nopen(s + "/a.py", "w")') == ["docs/x/a.py"]


def git(*words):
    return guard_tools.targets(["git", *words], cwd=os.getcwd())


def test_stash_unknown_subcommand_is_whole_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for w in (["$s"], ["-q", "$s"], ["$sub", "stash@{0}"]):
        assert git("stash", *w) == ["."]


def test_stash_message_values_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for w in (["-m", "$msg"], ["--message=$m"], ["push", "-m", "$m", "--", "$f"], ["list"], []):
        assert git("stash", *w) == [], w
    assert git("stash", "pop") == ["."]
