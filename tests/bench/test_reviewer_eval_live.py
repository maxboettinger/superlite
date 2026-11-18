"""reviewer_eval_live.py with every subprocess and model call faked; git runs for real in tmp repos."""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))
sys.path.insert(0, str(ROOT / "bench" / "experiments"))
import common  # noqa: E402
import reviewer_eval_live as live  # noqa: E402


def git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=n", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "src"
    r.mkdir()
    git(r, "init", "-q")
    (r / "a.py").write_text("for i in range(n - 1):\n    pass\n")
    git(r, "add", ".")
    git(r, "commit", "-qm", "one")
    base = git(r, "rev-parse", "HEAD")
    (r / "a.py").write_text("x = 1\nfor i in range(n - 1):\n    pass\n")
    git(r, "commit", "-qam", "two")
    merge = git(r, "rev-parse", "HEAD")
    return {"id": "pr-7", "repo": str(r), "base": base, "merge": merge, "title": "Fix loop", "body": "Body text"}


def test_checkout_detaches_at_merge_without_a_remote(repo, tmp_path):
    work = tmp_path / "work"
    clone = live.checkout(repo, work)
    assert clone == work / "pr-7"
    assert git(clone, "rev-parse", "HEAD") == repo["merge"]
    assert git(clone, "remote") == ""
    (clone / "stale.txt").write_text("x")
    again = live.checkout(repo, work)
    assert again == clone and not (clone / "stale.txt").exists()


def test_packet_writes_spec_and_returns_the_packet_path(tmp_path, monkeypatch):
    seen = {}

    def fake(cmd, cwd, env=None, timeout=600):
        seen["cmd"], seen["cwd"] = cmd, cwd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live, "_run", fake)
    case = {"id": "c", "base": "BASE", "title": "My title", "body": "My body"}
    out = live.packet(tmp_path, case)
    assert out == tmp_path / ".superlite" / "review-packet.md"
    spec = (tmp_path / ".superlite" / "spec.md").read_text()
    assert spec.startswith("# My title\n\nMy body")
    cmd = seen["cmd"]
    assert "packet" in cmd and "--inline" in cmd and "--spec" in cmd
    assert cmd[cmd.index("--base") + 1] == "BASE" and seen["cwd"] == tmp_path
    monkeypatch.setattr(live, "_run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom text"))
    with pytest.raises(live.LiveError, match="boom text"):
        live.packet(tmp_path, case)


def stream(text, cost=0.42):
    return "\n".join(json.dumps(e) for e in [{"type": "system"}, {"type": "result", "result": text, "total_cost_usd": cost}])


REPLY = ("Verdict: CHANGES_REQUESTED\n"
         "a.py:2 - off by one - use <= - tier 1 - quote: `for i in range(n - 1):`\n"
         "a.py:1 - ghost - drop it - tier 2 - quote: `not in the file at all`\n")


@pytest.fixture
def faked(repo, monkeypatch):
    seen = {"cmds": []}
    real_run = live._run

    def fake(cmd, cwd, env=None, timeout=600):
        if cmd and cmd[0] == "git":
            return real_run(cmd, cwd, env, timeout)
        if "packet" in cmd:
            (Path(cwd) / ".superlite").mkdir(exist_ok=True)
            (Path(cwd) / ".superlite" / "review-packet.md").write_text("packet")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        seen["cmds"].append(cmd)
        seen["env"] = env
        return SimpleNamespace(returncode=0, stdout=seen.get("stdout", stream(REPLY)), stderr="")

    monkeypatch.setattr(live, "_run", fake)
    return seen


def test_review_parses_verifies_and_fingerprints(repo, tmp_path, faked):
    out = live.review(repo, {"name": "current", "model": "opus", "effort": "high"}, tmp_path / "w")
    assert out["unverified"] == 1 and out["cost_usd"] == 0.42 and isinstance(out["seconds"], float)
    assert len(out["findings"]) == 1
    f = out["findings"][0]
    assert f["file"] == "a.py" and f["line"] == 2 and len(f["fp"]) == 10


def test_review_uses_the_variant_model_and_effort(repo, tmp_path, faked):
    live.review(repo, {"name": "v", "model": "sonnet", "effort": "low"}, tmp_path / "w")
    cmd = faked["cmds"][0]
    assert cmd[cmd.index("--agent") + 1] == "final-reviewer"
    assert json.loads(cmd[cmd.index("--agents") + 1])["final-reviewer"]["model"] == "sonnet"
    assert cmd[cmd.index("--effort") + 1] == "low"
    assert not any(k.startswith(("CLAUDE", "ANTHROPIC")) for k in faked["env"])


def test_review_model_failure_raises_live_error(repo, tmp_path, faked):
    faked["stdout"] = "no events here"
    with pytest.raises(live.LiveError, match="pr-7.*current"):
        live.review(repo, {"name": "current", "model": "opus", "effort": "high"}, tmp_path / "w")


def fake_ask(monkeypatch, reply, store=None):
    def ask(prompt, cwd, model="opus"):
        if store is not None:
            store.append(prompt)
        return common.Run([], 1.0, {"result": reply})

    monkeypatch.setattr(live, "_ask", ask)


def test_grade_parses_array_and_bad_reply_gives_no_grades(repo, monkeypatch):
    pooled = [{"fp": "f1", "file": "a.py", "line": 2, "problem": "p", "quote": "q"}]
    fake_ask(monkeypatch, 'Here: [{"fp": "f1", "grade": "real", "serious": true}, {"grade": "nit"}]')
    assert live.grade(repo, pooled) == {"f1": {"grade": "real", "serious": True}}
    fake_ask(monkeypatch, "no array")
    assert live.grade(repo, pooled) == {}


def test_grade_cuts_the_diff_to_60000_characters(repo, monkeypatch):
    prompts = []
    fake_ask(monkeypatch, "[]", prompts)
    monkeypatch.setattr(live, "_run", lambda cmd, cwd, env=None, timeout=600: SimpleNamespace(returncode=0, stdout="x" * 100000, stderr=""))
    live.grade(repo, [])
    p = prompts[0]
    assert "x" * 60000 in p and "x" * 60001 not in p
    assert p.split("x" * 60000)[1].startswith("\n(diff cut)")


def test_grade_prompt_hides_variant_names(repo, monkeypatch):
    prompts = []
    fake_ask(monkeypatch, "[]", prompts)
    live.grade(repo, [{"fp": "abc123def0", "file": "a.py", "line": 2, "problem": "off by one", "quote": "q"}])
    assert "abc123def0 | a.py:2 | off by one | q" in prompts[0]
    assert "current" not in prompts[0] and "variant" not in prompts[0].lower()


def test_parse_stream_reads_the_last_result():
    run = common.parse_stream(stream("hi"), 2.0)
    assert run.text == "hi" and run.cost == 0.42 and run.seconds == 2.0


def test_grade_diff_failure_raises_live_error(repo, monkeypatch):
    fake_ask(monkeypatch, "[]")
    monkeypatch.setattr(live, "_run", lambda cmd, cwd, env=None, timeout=600: SimpleNamespace(returncode=128, stdout="", stderr="bad object"))
    with pytest.raises(live.LiveError, match="bad object"):
        live.grade(repo, [])


def test_grade_skips_a_bracket_in_prose_before_the_array(repo, monkeypatch):
    pooled = [{"fp": "f1", "file": "a.py", "line": 2, "problem": "p", "quote": "q"}]
    fake_ask(monkeypatch, 'See [1] first: [{"fp": "f1", "grade": "wrong", "serious": false}] done [2]')
    assert live.grade(repo, pooled) == {"f1": {"grade": "wrong", "serious": False}}


def test_checkout_refuses_an_id_that_leaves_the_work_folder(repo, tmp_path):
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "f.txt").write_text("x")
    (tmp_path / "work").mkdir()
    with pytest.raises(live.LiveError):
        live.checkout({**repo, "id": "../keep"}, tmp_path / "work")
    assert (keep / "f.txt").exists()


def _timeout(*a, **k):
    raise subprocess.TimeoutExpired("cmd", 1)


def test_a_timeout_in_grade_git_or_packet_raises_live_error(repo, tmp_path, monkeypatch):
    fake_ask(monkeypatch, "[]")
    monkeypatch.setattr(live, "_ask", _timeout)
    with pytest.raises(live.LiveError, match="timed out"):
        live.grade(repo, [])
    monkeypatch.setattr(live, "_run", _timeout)
    with pytest.raises(live.LiveError, match="timed out"):
        live.grade(repo, [])
    with pytest.raises(live.LiveError, match="timed out"):
        live.checkout(repo, tmp_path / "work")
    with pytest.raises(live.LiveError, match="timed out"):
        live.packet(tmp_path, repo)
