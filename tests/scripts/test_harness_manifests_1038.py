# tests/scripts/test_harness_manifests_1038.py (#1038)
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOVED = (
    ".codex-plugin", ".cursor-plugin", ".devin-plugin", ".kimi-plugin", ".hermes-plugin",
    ".opencode", ".agents/plugins/marketplace.json", "index.js",
    "docs/README.opencode.md", "docs/README.kimi.md",
)
GONE_SECTIONS = ("Codex App", "Codex CLI", "Cursor", "Devin CLI", "Kimi Code", "OpenCode", "Hermes Agent")


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_removed_harness_files_are_gone():
    assert [rel for rel in REMOVED if (ROOT / rel).exists()] == []


def test_version_bump_lists_only_existing_files():
    files = json.loads(_read(".version-bump.json"))["files"]
    assert [f["path"] for f in files if not (ROOT / f["path"]).is_file()] == []
    assert [f["path"] for f in files] == [
        "package.json", ".claude-plugin/plugin.json", ".muse-plugin/plugin.json",
        ".claude-plugin/marketplace.json", ".muse-plugin/marketplace.json", "gemini-extension.json",
    ]


def test_package_json_has_no_main_and_keeps_pi():
    pkg = json.loads(_read("package.json"))
    assert "main" not in pkg
    assert pkg["type"] == "module"
    assert pkg["pi"] == {"extensions": ["./.pi/extensions/superlite.ts"], "skills": ["./skills"]}


def test_claude_code_and_pi_install_from_the_fork():
    readme = _read("README.md")
    assert readme.count("/plugin marketplace add maxboettinger/superlite") == 2
    assert readme.count("pi install git:github.com/maxboettinger/superlite") == 1
    assert "/plugin marketplace add iha2/superlite" not in readme
    assert "pi install git:github.com/iha2/superlite" not in readme
    assert readme.count("/plugin install superlite@superlite-dev") >= 3


def test_readme_drops_removed_harness_sections():
    readme = _read("README.md")
    headings = re.findall(r"^### (.+)$", readme, re.M)
    assert [h for h in headings if h in GONE_SECTIONS] == []
    for kept in ("Claude Code", "Antigravity", "Factory Droid", "Gemini CLI", "Pi", "Muse"):
        assert kept in headings, kept
    for ref in (".agents/plugins", ".cursor-plugin", ".opencode", "README.kimi.md", "README.opencode.md"):
        assert ref not in readme, ref
    assert "Installs for Pi, Gemini CLI and the other harnesses are in [Installation](#installation) below." in readme


def test_agents_md_names_no_removed_harness_file():
    text = _read("AGENTS.md")
    for ref in REMOVED + ("hooks-cursor.json",):
        assert ref not in text, ref
    assert "| Pi | `.pi/extensions/superlite.ts`, `package.json` |" in text
