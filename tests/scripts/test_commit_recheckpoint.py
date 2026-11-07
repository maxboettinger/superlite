"""commit_task: a re-run with no change since the task's checkpoint says so (#294)."""
import json
import re
import sys

from test_autocommit import ENV, SCRIPTS, checkpoint, git, make_repo, run, write  # noqa: F401

sys.path.insert(0, str(SCRIPTS))


def setup(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "def parse(t):\n    return t.split()\n")
    write(repo, "tests/test_a.py", "def test_p():\n    assert 1\n")
    return repo


def msg(tid, sha):
    return f"{tid}: no change since its last checkpoint {sha}"


def test_recheckpoint_without_change_prints_message(tmp_path):
    repo = setup(tmp_path)
    s1 = checkpoint(repo, "T1").stdout.strip()
    r = checkpoint(repo, "T1")
    assert r.returncode == 0, r.stderr
    assert r.stdout == msg("T1", s1) + "\n"
    st = json.loads((repo / ".superlite/checkpoints.json").read_text())
    assert [e["task"] for e in st["entries"]] == ["T1"]
    lines = [ln for ln in (repo / ".superlite/progress.md").read_text().splitlines() if ln.startswith("- commit T1 ")]
    assert len(lines) == 1


def test_recheckpoint_after_another_task_names_its_own_sha(tmp_path):
    repo = setup(tmp_path)
    s1 = checkpoint(repo, "T1").stdout.strip()
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n")
    assert checkpoint(repo, "T2").returncode == 0
    r = checkpoint(repo, "T1")
    assert r.stdout == msg("T1", s1) + "\n"


def test_several_tasks_mix_lines(tmp_path):
    repo = setup(tmp_path)
    s1 = checkpoint(repo, "T1").stdout.strip()
    write(repo, "src/b.py", "def lex(t):\n    return list(t)\n")
    r = checkpoint(repo, "T1", "T2")
    assert r.returncode == 0, r.stderr
    l1, l2 = r.stdout.splitlines()
    assert l1 == msg("T1", s1)
    m = re.fullmatch(r"T2 ([0-9a-f]{40})", l2)
    assert m
    assert git(repo, "rev-parse", m.group(1) + "^") == s1


def test_recheckpoint_with_change_prints_bare_sha(tmp_path):
    repo = setup(tmp_path)
    s1 = checkpoint(repo, "T1").stdout.strip()
    write(repo, "src/a.py", "def parse(t):\n    return t\n")
    out = checkpoint(repo, "T1").stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", out) and out != s1


def test_reuse_writes_ledger_line_when_missing(tmp_path):
    repo = setup(tmp_path)
    s1 = checkpoint(repo, "T1").stdout.strip()
    led = repo / ".superlite/progress.md"
    led.write_text("".join(ln + "\n" for ln in led.read_text().splitlines() if not ln.startswith("- commit T1")))
    r = checkpoint(repo, "T1")
    assert r.stdout == msg("T1", s1) + "\n"
    lines = [ln for ln in led.read_text().splitlines() if ln.startswith(f"- commit T1 {s1[:10]}")]
    assert len(lines) == 1


def inproc(repo, monkeypatch):
    import commit_task
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    for k in ("SUPERLITE_SL", "SL_TEST_PYTHON", "SUPERLITE_PROBE_RUN"):
        monkeypatch.setenv(k, ENV[k])
    return commit_task


def test_reuse_launches_no_probe_or_seam_check(tmp_path, monkeypatch, capsys):
    repo = setup(tmp_path)
    ct = inproc(repo, monkeypatch)
    probes, seams = [], []
    monkeypatch.setattr(ct, "launch_probes", lambda *a, **k: probes.append(a))
    monkeypatch.setattr(ct, "launch_seam_checks", lambda *a, **k: seams.append(a))
    assert ct.main(["T1", "--plan", "plan.md"]) == 0
    s1 = capsys.readouterr().out.strip()
    assert len(probes) == 1
    n_seams = len(seams)
    assert ct.main(["T1", "--plan", "plan.md"]) == 0
    assert len(probes) == 1 and len(seams) == n_seams
    assert capsys.readouterr().out == msg("T1", s1) + "\n"


def test_reuse_releases_the_agent(tmp_path):
    repo = setup(tmp_path)
    checkpoint(repo, "T1")
    pool = repo / ".superlite/pool.json"
    pool.write_text(json.dumps({"agents": [{"id": "a1", "tasks": [], "busy": True, "current": "T1"}]}))
    assert checkpoint(repo, "T1").returncode == 0
    a1 = json.loads(pool.read_text())["agents"][0]
    assert a1["busy"] is False and not a1.get("current") and "T1" in a1["tasks"]


def test_dispatch_after_reuse_still_prints_next(tmp_path):
    repo = setup(tmp_path)
    checkpoint(repo, "T1")
    r = run("commit_task", "T1", "--plan", "plan.md", "--dispatch", cwd=repo)
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[0].startswith("T1: no change since its last checkpoint ")
    assert "next:" in lines


def test_commit_one_without_unchanged_attribute(tmp_path, monkeypatch, capsys):
    repo = setup(tmp_path)
    ct = inproc(repo, monkeypatch)
    monkeypatch.setattr(ct, "launch_probes", lambda *a, **k: None)
    monkeypatch.setattr(ct, "launch_seam_checks", lambda *a, **k: None)
    assert ct.main(["T1", "--plan", "plan.md"]) == 0
    s1 = capsys.readouterr().out.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", s1)
    assert ct.main(["T1", "--plan", "plan.md"]) == 0
    assert capsys.readouterr().out == msg("T1", s1) + "\n"
