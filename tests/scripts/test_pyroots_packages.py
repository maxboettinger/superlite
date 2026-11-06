import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import pyroots  # noqa: E402

PLAN_LINE = "**Produces:** review.shell.run_json(argv: list[str]) -> dict\n"


def mk(root, rel, text=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def plan(root, text=PLAN_LINE):
    mk(root, "plan.md", text)
    return str(root / "plan.md")


def test_src_package_not_a_root(tmp_path):
    for f in ("src/pkg/__init__.py", "src/pkg/connectors/__init__.py", "src/pkg/connectors/base.py"):
        mk(tmp_path, f)
    p = plan(tmp_path, "**Produces:** connectors.base.Foo() -> int\n")
    assert pyroots.import_roots(tmp_path, p) == []


def test_folder_inside_package_not_a_root(tmp_path):
    mk(tmp_path, "app/__init__.py")
    mk(tmp_path, "app/data/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path, "**Produces:** review.shell.run_json(\n")) == []


def test_folder_under_found_root_not_a_root(tmp_path):
    mk(tmp_path, "x/review/shell.py")
    mk(tmp_path, "x/y/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path, "**Produces:** review.shell.run_json(\n")) == ["x"]


def test_root_init_does_not_block(tmp_path):
    mk(tmp_path, "__init__.py")
    mk(tmp_path, "x/y/mod.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path, "**Produces:** mod.f(a) -> int\n")) == ["x/y"]
