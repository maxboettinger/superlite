"""#1046: only Claude Code and Pi remain: no Gemini, Muse, Antigravity, Codex or Hermes file, README section or AGENTS.md row."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills" / "using-superlite" / "references"
REMOVED = ("GEMINI.md", "gemini-extension.json", ".muse-plugin",
           *(f"skills/using-superlite/references/{h}-tools.md" for h in ("antigravity", "codex", "gemini", "hermes", "muse")))
GONE_WORDS = ("Antigravity", "Factory Droid", "Gemini", "Copilot", "Grok", "Qwen", "Muse", "Codex", "Hermes",
              "iha2/superlite")


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_removed_harness_files_are_gone():
    assert [rel for rel in REMOVED if (ROOT / rel).exists()] == []


def test_only_claude_code_and_pi_tool_mappings_remain():
    assert sorted(p.name for p in REFS.glob("*-tools.md")) == ["claude-code-tools.md", "pi-tools.md"]


def test_version_bump_lists_three_files():
    data = json.loads(_read(".version-bump.json"))
    assert [f["path"] for f in data["files"]] == ["package.json", ".claude-plugin/plugin.json",
                                                   ".claude-plugin/marketplace.json"]
    assert "scripts/bump-version.sh" in data["audit"]["exclude"]


def test_readme_installs_only_claude_code_and_pi():
    readme = _read("README.md")
    install = readme.split("\n## Installation\n", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.+)$", install, re.M) == ["Claude Code", "Pi", "Keeping versions in sync"]
    assert [w for w in GONE_WORDS if w in readme] == []
    assert "The Pi install is in [Installation](#installation) below." in readme
    assert "superlite runs on Claude Code and Pi. If you use both," in readme
    assert "(Pi, plus Claude Code notes)" in readme


def test_agents_md_harness_table_is_claude_code_and_pi():
    text = _read("AGENTS.md")
    table = text.split("## Harness files", 1)[1].split("\n## ", 1)[0]
    rows = [ln.split("|")[1].strip() for ln in table.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert rows == ["Harness", "Claude Code", "Pi"]
    assert [w for w in GONE_WORDS if w in text] == []


def test_docs_name_no_removed_manifest():
    assert "gemini-extension.json" not in _read("docs/testing.md")
    assert "Hermes" not in _read("scripts/bump-version.sh")
