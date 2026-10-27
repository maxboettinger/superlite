import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import pyroots  # noqa: E402

HY = "config/skills/reviewing-periods/scripts"
PLAN_LINE = "**Produces:** review.shell.run_json(argv: list[str]) -> dict\n"


def mk(root, rel, text=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def cfg(root, data):
    mk(root, ".superlite/test-cmd.json", data if isinstance(data, str) else json.dumps(data))


def plan(root, text=PLAN_LINE):
    mk(root, "plan.md", text)
    return str(root / "plan.md")


def test_config_key_wins(tmp_path):
    cfg(tmp_path, {"test": "pytest", "pythonpath": ["a/b"]})
    mk(tmp_path, f"{HY}/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path)) == ["a/b"]


def test_derived_from_produces_hyphen_dir(tmp_path):
    mk(tmp_path, f"{HY}/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path)) == [HY]


def test_derived_package_init(tmp_path):
    mk(tmp_path, f"{HY}/review/shell/__init__.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path)) == [HY]


def test_two_part_name(tmp_path):
    mk(tmp_path, "x/y/mod.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path, "**Produces:** mod.f(a) -> int\n")) == ["x/y"]


def test_root_and_src_never_returned(tmp_path):
    mk(tmp_path, "review/shell.py")
    mk(tmp_path, "src/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path)) == []


def test_skips_hidden_venv_node_modules(tmp_path):
    for d in (".venv", "node_modules", ".hidden", "site-packages", "__pycache__"):
        mk(tmp_path, f"{d}/review/shell.py")
    assert pyroots.import_roots(tmp_path, plan(tmp_path)) == []


def test_deduped_sorted(tmp_path):
    mk(tmp_path, f"{HY}/review/shell.py")
    mk(tmp_path, f"{HY}/review/model.py")
    txt = PLAN_LINE + "**Produces:** review.model.X(a) -> int\n"
    assert pyroots.import_roots(tmp_path, plan(tmp_path, txt)) == [HY]


def test_sorted_two_roots(tmp_path):
    mk(tmp_path, "zz/review/shell.py")
    mk(tmp_path, "aa/review/model.py")
    txt = PLAN_LINE + "**Produces:** review.model.X(a) -> int\n"
    assert pyroots.import_roots(tmp_path, plan(tmp_path, txt)) == ["aa", "zz"]


def test_bad_json_or_non_list_key(tmp_path):
    mk(tmp_path, f"{HY}/review/shell.py")
    p = plan(tmp_path)
    for bad in ("{not json", json.dumps({"pythonpath": "a/b"}), json.dumps({"pythonpath": [1, 2]}), "[]"):
        cfg(tmp_path, bad)
        assert pyroots.import_roots(tmp_path, p) == [HY]


def test_missing_plan_file_is_empty(tmp_path):
    assert pyroots.import_roots(tmp_path, str(tmp_path / "nope.md")) == []
    assert pyroots.import_roots(tmp_path) == []
    assert pyroots.import_roots(tmp_path, None) == []


def test_relative_plan_path(tmp_path):
    mk(tmp_path, f"{HY}/review/shell.py")
    plan(tmp_path)
    assert pyroots.import_roots(tmp_path, "plan.md") == [HY]
