import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
from test_autocommit import make_repo, two_tasks, run, git  # noqa: E402
import autocommit  # noqa: E402


def test_base_of():
    assert autocommit.base_of({"base": "abc", "head": "abc"}) == "abc"
    assert autocommit.base_of({"head": "def"}) == "def"


def test_checkpoint_state_names_base(tmp_path):
    repo = make_repo(tmp_path)
    start = git(repo, "rev-parse", "HEAD")
    two_tasks(repo)
    st = json.loads((repo / ".superlite" / "checkpoints.json").read_text())
    assert st["base"] == start and st["head"] == st["base"]


def test_legacy_state_without_base(tmp_path):
    repo = make_repo(tmp_path)
    start = git(repo, "rev-parse", "HEAD")
    two_tasks(repo)
    p = repo / ".superlite" / "checkpoints.json"
    st = json.loads(p.read_text())
    del st["base"]
    p.write_text(json.dumps(st))
    r = run("autocommit", "status", cwd=repo)
    assert r.returncode == 0 and f"(base {start[:10]})" in r.stdout
    assert run("autocommit", "apply", cwd=repo).returncode == 0
