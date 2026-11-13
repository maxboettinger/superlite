"""#712: pyroots names the directory a pythonpath entry needs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import pyroots  # noqa: E402


def mk(root, rel, text=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def tools_pkg(root):
    mk(root, "tools/pkg/__init__.py")
    mk(root, "tools/pkg/b.py", "Y = 1\n")


def test_advice_without_key(tmp_path):
    assert pyroots.advice(tmp_path, ["tools"]) == 'add "pythonpath": ["tools"] to .superlite/test-cmd.json'


def test_advice_with_key(tmp_path):
    mk(tmp_path, ".superlite/test-cmd.json", json.dumps({"pythonpath": ["lib"]}))
    assert pyroots.advice(tmp_path, ["tools", "a", "tools"]) == 'add "a", "tools" to "pythonpath" in .superlite/test-cmd.json'


def test_hint_package_parent(tmp_path):
    tools_pkg(tmp_path)
    assert pyroots.hint(tmp_path, "pkg", [], "tools/pkg/a.py") == "tools"


def test_hint_namespace_package(tmp_path):
    mk(tmp_path, "tools/pkg/b.py")
    assert pyroots.hint(tmp_path, "pkg", [], "tools/pkg/a.py") == "tools"


def test_hint_flat_sibling(tmp_path):
    mk(tmp_path, "scripts/helper.py")
    assert pyroots.hint(tmp_path, "helper", [], "scripts/run.py") == "scripts"


def test_hint_none_when_root_src_or_a_root_resolves(tmp_path):
    tools_pkg(tmp_path)
    assert pyroots.hint(tmp_path, "pkg", ["tools"], "tools/pkg/a.py") is None
    mk(tmp_path, "src/pkg/b.py")
    assert pyroots.hint(tmp_path, "pkg", [], "tools/pkg/a.py") is None


def test_hint_walks_the_repo_after_the_ancestors(tmp_path):
    mk(tmp_path, "libs/shared/__init__.py")
    mk(tmp_path, "z/deep/er/shared.py")
    assert pyroots.hint(tmp_path, "shared", [], "app/main.py") == "libs"
    assert pyroots.hint(tmp_path, "shared", [], "app/main.py", walk=False) is None


def test_hint_ignores_folders_without_python_and_skipped_dirs(tmp_path):
    mk(tmp_path, "docs/pkg/readme.md")
    mk(tmp_path, ".venv/lib/pkg/__init__.py")
    mk(tmp_path, "node_modules/x/pkg.py")
    assert pyroots.hint(tmp_path, "pkg", [], "tools/a.py") is None


def test_owned_hint_new_files(tmp_path):
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", [], {"tools/pkg/__init__.py"}) == "tools"
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", []) == "tools"
    assert pyroots.owned_hint(tmp_path, "a/b/c/x.py", []) == "a/b"
    assert pyroots.owned_hint(tmp_path, "tools/a.py", []) is None
    assert pyroots.owned_hint(tmp_path, "a.py", []) is None


def test_owned_hint_none_for_src_roots_packages_and_odd_names(tmp_path):
    (tmp_path / "src").mkdir()
    assert pyroots.owned_hint(tmp_path, "src/pkg/a.py", []) is None
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", ["tools"]) is None
    assert pyroots.owned_hint(tmp_path, "pkg/sub/a.py", [], {"pkg/__init__.py", "pkg/sub/__init__.py"}) is None
    assert pyroots.owned_hint(tmp_path, "my-tools/pkg/a.py", []) is None
    assert pyroots.owned_hint(tmp_path, "tools/pkg/notes.md", []) is None


def test_owned_hint_existing_file_reads_its_imports(tmp_path):
    tools_pkg(tmp_path)
    mk(tmp_path, "tools/pkg/a.py", "import os\nfrom pkg import b\n")
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", []) == "tools"
    mk(tmp_path, "tools/pkg/a.py", "import json\nfrom tools.pkg import b\nfrom . import b as c\n")
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", []) is None


def test_owned_hint_unparsable_file_uses_its_folder(tmp_path):
    mk(tmp_path, "tools/pkg/a.py", "def broken(:\n")
    assert pyroots.owned_hint(tmp_path, "tools/pkg/a.py", []) == "tools"
