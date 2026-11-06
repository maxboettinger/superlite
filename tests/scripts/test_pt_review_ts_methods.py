"""#238: pt_review contract finds TypeScript and JavaScript class method declarations."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review", SCRIPT)
pt_review = importlib.util.module_from_spec(_spec)
sys.modules["pt_review"] = pt_review
_spec.loader.exec_module(pt_review)

STORE_TS = (
    "export class Store {\n"
    "  private items: Item[] = [];\n"
    "  static create<T extends Map<string, number>>(seed: T): Store {\n"
    "    return new Store();\n"
    "  }\n"
    "  async fetchAll(opts: Opts): Promise<Item[]> {\n"
    "    await this.load();\n"
    "    return this.items;\n"
    "  }\n"
    "  get size(): number {\n"
    "    return this.items.length;\n"
    "  }\n"
    "  private helper(): void {\n"
    "    flush();\n"
    "  }\n"
    "  public save(cb: (e: Error) => void): void {\n"
    "    this.helper();\n"
    "  }\n"
    "}\n")

PLAN = """# web plan

```mermaid
flowchart LR
%% taskgraph
T1 --> T2
```

### T1 store · Complexity 3
**Owns:** src/store.ts, tests/store.test.ts
**Produces:** Store.fetchAll(opts: Opts) -> Promise<Item[]>

### T2 view · Complexity 3
**Owns:** src/view.ts, tests/view.test.ts
**Consumes:** Store.fetchAll(opts: Opts) -> Promise<Item[]> (T1)
**Produces:** View.render(items: Item[]) -> string

## Review Focus
- web: state
"""


def project(tmp_path: Path, plan: str = PLAN) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "store.ts").write_text(STORE_TS, encoding="utf-8")
    (tmp_path / "src" / "view.ts").write_text(
        "export class View {\n  render(items: Item[]): string {\n    return '';\n  }\n}\n", encoding="utf-8")
    (tmp_path / "plan.md").write_text(plan, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("name, line", [("Store", 1), ("create", 3), ("fetchAll", 6), ("size", 10), ("helper", 13), ("save", 16)])
def test_ts_class_methods_are_declared(tmp_path, name, line):
    project(tmp_path)
    assert pt_review.find_declaration(tmp_path, ["src/store.ts"], name) == ("src/store.ts", line)


def test_calls_are_not_declarations(tmp_path):
    (tmp_path / "app.js").write_text(
        "export function main() {\n"
        "  load();\n"
        "  this.flush();\n"
        "  await fetchAll();\n"
        "  const r = render(x);\n"
        "  stream(x).then(() => {\n"
        "  loadMore(x)\n"
        "  items: [],\n"
        "}\n", encoding="utf-8")
    find = pt_review.find_declaration
    for name in ("load", "flush", "fetchAll", "render", "stream", "loadMore", "items"):
        assert find(tmp_path, ["app.js"], name) is None, name
    assert find(tmp_path, ["app.js"], "main") == ("app.js", 1)


def test_multiline_heads_and_signatures_are_declared(tmp_path):
    (tmp_path / "shape.ts").write_text(
        "export abstract class Shape {\n"
        "  abstract area(): number;\n"
        "  protected override render(\n"
        "    ctx: Ctx,\n"
        "  ) {\n"
        "  }\n"
        "  async *walk(): AsyncGenerator<number> {\n"
        "  }\n"
        "}\n"
        "export interface Repo {\n"
        "  find?(id: string): Item;\n"
        "}\n", encoding="utf-8")
    find = pt_review.find_declaration
    assert find(tmp_path, ["shape.ts"], "area") == ("shape.ts", 2)
    assert find(tmp_path, ["shape.ts"], "render") == ("shape.ts", 3)
    assert find(tmp_path, ["shape.ts"], "walk") == ("shape.ts", 7)
    assert find(tmp_path, ["shape.ts"], "find") == ("shape.ts", 11)


def test_contract_verifies_a_ts_class_method(tmp_path, capsys):
    proj = project(tmp_path)
    assert pt_review.main(["contract", "--plan", str(proj / "plan.md"), "--root", str(proj), "--seam", "T1,T2"]) == 0
    out = capsys.readouterr().out
    assert "checked by declaration" in out and "not declared" not in out


def test_contract_reports_a_missing_ts_method(tmp_path, capsys):
    proj = project(tmp_path, PLAN.replace("Store.fetchAll(", "Store.fetchMissing("))
    assert pt_review.main(["contract", "--plan", str(proj / "plan.md"), "--root", str(proj), "--seam", "T1,T2"]) == 1
    out = capsys.readouterr().out
    assert "T1 Produces: `fetchMissing` not declared in src/store.ts" in out


def test_generator_private_and_generic_callback_heads_are_declared(tmp_path):
    (tmp_path / "gen.ts").write_text(
        "class G {\n"
        "  /**\n"
        "   * walk(x): number {\n"
        "   */\n"
        "  *walk() {\n"
        "  }\n"
        "  #secret(x: number) {\n"
        "  }\n"
        "  pick<T extends (a: number) => void>(fn: T): void {\n"
        "  }\n"
        "}\n", encoding="utf-8")
    find = pt_review.find_declaration
    assert find(tmp_path, ["gen.ts"], "walk") == ("gen.ts", 5)
    assert find(tmp_path, ["gen.ts"], "secret") == ("gen.ts", 7)
    assert find(tmp_path, ["gen.ts"], "pick") == ("gen.ts", 9)


def test_long_lines_do_not_backtrack(tmp_path):
    import time
    (tmp_path / "long.ts").write_text("  foo<" + "a" * 20000 + "(" + "x, " * 20000 + "\n", encoding="utf-8")
    t = time.time()
    pt_review.find_declaration(tmp_path, ["long.ts"], "foo")
    assert time.time() - t < 2


def test_wrapped_and_callback_calls_are_not_declarations(tmp_path):
    (tmp_path / "app.ts").write_text(
        "  render(\n    x,\n  );\n"
        "  subscribe((e) => {\n    log(e);\n  });\n"
        "  useEffect(() => {\n  }, []);\n"
        "  fetchAll(\n    opts: Opts,\n  ): Promise<Item[]> {\n  }\n", encoding="utf-8")
    find = pt_review.find_declaration
    for name in ("render", "subscribe", "useEffect"):
        assert find(tmp_path, ["app.ts"], name) is None, name
    assert find(tmp_path, ["app.ts"], "fetchAll") == ("app.ts", 9)
