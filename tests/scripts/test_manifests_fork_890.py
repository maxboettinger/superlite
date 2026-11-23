# tests/scripts/test_manifests_fork_890.py (#890)
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORK = "https://github.com/maxboettinger/superlite"


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_package_json_urls_name_the_fork():
    pkg = _load("package.json")
    assert pkg["homepage"] == FORK
    assert pkg["repository"] == {"type": "git", "url": f"git+{FORK}.git"}


def test_authors_stay_upstream():
    assert _load("package.json")["author"] == "CWogu"
    assert _load(".claude-plugin/plugin.json")["author"] == {"name": "CWogu"}


def test_claude_manifests_name_no_upstream_repo():
    for rel in ("package.json", ".claude-plugin/plugin.json"):
        assert "iha2/superlite" not in (ROOT / rel).read_text(encoding="utf-8"), rel
