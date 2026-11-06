"""wave0: the resolved language is named alone; existing files get no stub; raw items are marked no_stub."""
from __future__ import annotations

import json

from test_plan_tools import run
from test_wave0 import PY, WAVE0, plan


def section(tmp_path):
    b = (tmp_path / ".superlite" / "briefs" / "wave0.md").read_text(encoding="utf-8")
    return b.split("## Language and layout")[1].split("\n## ")[0]


def meta(tmp_path):
    return json.loads((tmp_path / ".superlite" / "briefs" / "wave0.json").read_text(encoding="utf-8"))


def yaml_of(tmp_path):
    return (tmp_path / ".superlite" / "briefs" / "wave0.md").read_text(encoding="utf-8").split("```yaml")[1].split("```")[0]


def build(tmp_path, stack, tasks=PY):
    p = plan(tmp_path, stack, "none", tasks)
    cp = run(WAVE0, "--plan", p, cwd=tmp_path)
    assert cp.returncode == 0, cp.both


def test_resolved_language_named_alone(tmp_path):
    (tmp_path / "Package.swift").write_text("// swift\n", encoding="utf-8")
    build(tmp_path, "**Tech stack:** Swift 6; a TypeScript dashboard in web/app.ts and a .NET bridge")
    s = section(tmp_path)
    assert "The project's language: Swift" in s
    assert "TypeScript" not in s and "C#" not in s


def test_test_cmd_json_language_wins(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "kotlin", "test": "gradle test"}), encoding="utf-8")
    build(tmp_path, "**Tech stack:** Python 3.12")
    assert "The project's language: Kotlin" in section(tmp_path)


def test_fallback_names_swift(tmp_path):
    build(tmp_path, "**Tech stack:** Swift 6, SwiftUI")
    assert "The plan names: Swift" in section(tmp_path)


def test_host_name_is_not_csharp(tmp_path):
    build(tmp_path, "**Tech stack:** Python; docs at example.net")
    s = section(tmp_path)
    assert "Python" in s and "C#" not in s


def test_existing_file_gets_no_stub(tmp_path):
    f = tmp_path / "src/pkg/slug.py"
    f.parent.mkdir(parents=True)
    f.write_text("def slugify(text): ...\n", encoding="utf-8")
    build(tmp_path, "**Tech stack:** Python")
    m = meta(tmp_path)
    assert m["stubs"] == [] and m["wait"] == []
    assert "id: T1" not in yaml_of(tmp_path)


def raw_plan(tmp_path, t1_produces):
    t1 = {"tid": "T1", "title": "slug", "owns": "src/pkg/slug.py, tests/test_slug.py", "produces": t1_produces}
    t2 = {"tid": "T2", "title": "feed", "owns": "src/pkg/feed.py", "produces": "pkg.feed.build(items: list[str]) -> str",
          "extra": "**Consumes:** " + t1_produces + "\n"}
    build(tmp_path, "**Tech stack:** Python", [t1, t2])


def test_raw_item_marked_no_stub(tmp_path):
    raw_plan(tmp_path, "pkg.slug.slugify(text: str) -> str · `pkg.slug.SLUG_MAX`")
    y = yaml_of(tmp_path)
    assert 'name: "pkg.slug.slugify"' in y
    assert '{no_stub: "`pkg.slug.SLUG_MAX`"}' in y
    assert "raw:" not in y


def test_only_raw_items_no_entry(tmp_path):
    raw_plan(tmp_path, "`pkg.slug.SLUG_MAX`")
    m = meta(tmp_path)
    assert m["stubs"] == [] and m["wait"] == []
