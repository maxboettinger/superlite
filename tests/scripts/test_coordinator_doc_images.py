import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
LINE = ("- New code belongs to an implementer task. You may write only docs/plans/**, docs/*/plans/**, "
        "SPEC*.md, docs/**/*.md, docs/** images (png, jpg, jpeg, gif, svg, webp), any docs.md and "
        ".superlite/**, and rm a file git does not track and no task Owns.")


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "pool.json").write_text("{}")
    return tmp_path


def run(proj, tool, tool_input, **extra):
    raw = json.dumps({"tool_name": tool, "tool_input": tool_input, **extra})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    for k in ("SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_ROLE", "SUPERLITE_STATE_DIR", "SUPERLITE_SESSION_ID"):
        env.pop(k, None)
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def last_row(proj):
    return json.loads((proj / ".superlite" / "incidents.jsonl").read_text().splitlines()[-1])


@pytest.mark.parametrize("ext", ["png", "jpg", "jpeg", "gif", "svg", "webp"])
@pytest.mark.parametrize("absolute", [True, False])
def test_write_doc_image_passes(proj, ext, absolute):
    rel = f"docs/ui/mock.{ext}"
    r = run(proj, "Write", {"file_path": str(proj / rel) if absolute else rel})
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("rel", ["src/mock.png", "docs/../src/a.png"])
def test_image_outside_docs_blocks(proj, rel):
    assert run(proj, "Write", {"file_path": rel}).returncode == 2


def test_human_mode_doc_image_blocks(proj):
    (proj / ".superlite" / "orchestrator.json").write_text(json.dumps({"mode": "human", "approved": False}))
    assert run(proj, "Write", {"file_path": "docs/ui/mock.png"}).returncode == 2


def test_block_message_line(proj):
    r = run(proj, "Write", {"file_path": "src/a.py"})
    assert r.returncode == 2 and LINE in r.stderr


def test_rows_carry_rule_and_cwd(proj):
    r = run(proj, "Write", {"file_path": "src/a.py"}, cwd="/w/x")
    assert r.returncode == 2
    row = last_row(proj)
    assert row["rule"] == "code" and row["cwd"] == "/w/x"
    run(proj, "Write", {"file_path": ".superlite/orchestrator.json"}, cwd="/w/x")
    assert last_row(proj)["rule"] == "protected"
    run(proj, "Write", {"file_path": "src/a.py"})
    assert last_row(proj)["cwd"] == ""
    (proj / ".superlite" / "fleet.json").write_text('{"on": true}')
    r = run(proj, "Agent", {"subagent_type": "superlite:implementer"}, cwd="/w/x")
    assert r.returncode == 2
    row = last_row(proj)
    assert row["rule"] == "fleet" and row["cwd"] == "/w/x"


def test_human_rule_row(proj):
    (proj / ".superlite" / "orchestrator.json").write_text(json.dumps({"mode": "human", "approved": False}))
    run(proj, "Write", {"file_path": "src/a.py"}, cwd="/w/x")
    assert last_row(proj)["rule"] == "human"
