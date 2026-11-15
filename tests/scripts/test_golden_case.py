import json, os, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import golden_case as gc  # noqa: E402

REQ = {"id": "small", "size": "small", "topic": "golden-small", "base": "b", "merge": "m", "issues": [], "test_cmd": "x", "hidden_tests": []}


def put(root, cid, **over):
    d = root / "bench" / "golden" / cid; d.mkdir(parents=True, exist_ok=True)
    (d / "case.json").write_text(json.dumps({**REQ, "id": cid, **over}), encoding="utf-8")
    return d


def test_load_adds_dir(tmp_path):
    d = put(tmp_path, "small", baseline={"lead_usd": 1.0})
    c = gc.load(d)
    assert c["dir"] == str(d.resolve()) and c["baseline"] == {"lead_usd": 1.0} and c["base"] == "b"


def test_load_missing_key(tmp_path):
    d = put(tmp_path, "small"); j = json.loads((d / "case.json").read_text()); del j["base"]
    (d / "case.json").write_text(json.dumps(j))
    with pytest.raises(gc.CaseError, match="base"):
        gc.load(d)


def test_load_bad_json(tmp_path):
    d = put(tmp_path, "small"); (d / "case.json").write_text("{nope")
    with pytest.raises(gc.CaseError, match="case.json"):
        gc.load(d)


@pytest.mark.parametrize("p", ["../x.py", "/etc/x.py", "tests/../../x.py", "C:/x.py", "a\\b.py"])
def test_hidden_path_escape(tmp_path, p):
    d = put(tmp_path, "small", hidden_tests=[{"path": p, "text": "t"}])
    with pytest.raises(gc.CaseError):
        gc.load(d)


def test_cases_empty(tmp_path):
    assert gc.cases(tmp_path) == []


def test_cases_order(tmp_path):
    for c in ("large", "small", "typical"):
        put(tmp_path, c)
    assert [c["id"] for c in gc.cases(tmp_path)] == ["small", "typical", "large"]


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, env=env, capture_output=True, text=True, check=True)
    return r.stdout.strip()


HIDDEN = "def test_new():\n    import src.a as a\n    assert a.V == 2  # \u00e4\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "src").mkdir(); (tmp_path / "src" / "a.py").write_text("V = 1\n"); (tmp_path / "src" / "__init__.py").write_text("")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "base"); base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "src" / "a.py").write_text("V = 2\n"); (tmp_path / "tests").mkdir(); (tmp_path / "tests" / "test_new.py").write_text(HIDDEN, encoding="utf-8")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-q", "-m", "merge"); merge = git(tmp_path, "rev-parse", "HEAD")
    real = gc._run
    prs = {"mergeCommit": {"oid": merge}, "title": "t", "closingIssuesReferences": [{"number": 7}]}

    def run(cmd, cwd=None, timeout=None):
        if cmd[0] == "gh":
            if cmd[1] == "pr":
                return 0, json.dumps(prs)
            return 0, json.dumps({"title": "T7", "body": "B7"})
        return real(cmd, cwd, timeout)
    monkeypatch.setattr(gc, "_run", run)
    return tmp_path, base, merge


def test_make_from_pr(repo):
    root, base, merge = repo
    d = gc.make(root, 5, "small", "small")
    j = json.loads((d / "case.json").read_text(encoding="utf-8"))
    assert d == root / "bench" / "golden" / "small" and j["base"] == base and j["merge"] == merge
    assert j["hidden_tests"] == [{"path": "tests/test_new.py", "text": HIDDEN}]
    assert j["issues"] == [{"number": 7, "title": "T7", "body": "B7"}] and j["baseline"] == {}
    assert gc.load(d)["id"] == "small"


def test_make_no_new_tests(repo, tmp_path_factory, monkeypatch):
    root, base, merge = repo
    real = gc._run
    monkeypatch.setattr(gc, "_run", lambda cmd, cwd=None, timeout=None: (0, json.dumps({"mergeCommit": {"oid": base}, "closingIssuesReferences": []}))
                        if cmd[0] == "gh" else real(cmd, cwd, timeout))
    git(root, "commit", "-q", "--allow-empty", "-m", "x")
    # base^1 does not exist for the root commit; use merge-less pr: a commit that adds no tests
    (root / "src" / "b.py").write_text("x\n"); git(root, "add", "."); git(root, "commit", "-q", "-m", "nt")
    monkeypatch.setattr(gc, "_run", lambda cmd, cwd=None, timeout=None: (0, json.dumps({"mergeCommit": {"oid": git(root, 'rev-parse', 'HEAD')}, "closingIssuesReferences": []}))
                        if cmd[0] == "gh" else real(cmd, cwd, timeout))
    with pytest.raises(gc.CaseError, match="PR 9 adds no test file"):
        gc.make(root, 9, "x", "small")


def test_make_baseline(repo):
    root, _, _ = repo
    row = lambda b, c: {"v": 1, "row": "batch", "batch": b, "lead": {"cost_usd": c, "turns": 60, "wall_s": 1740}, "workers_total": {"cost_usd": 0.47}}
    (root / ".superlite").mkdir()
    (root / ".superlite" / "batch-costs.jsonl").write_text("\n".join(json.dumps(r) for r in (row("B7", 9.0), row("B7", 3.1), row("B8", 1.0))) + "\n")
    j = json.loads((gc.make(root, 5, "small", "small", batch="B7") / "case.json").read_text())
    assert j["baseline"] == {"lead_usd": 3.1, "total_usd": 3.57, "lead_turns": 60, "wall_min": 29.0}


def case_for(repo):
    root, base, merge = repo
    c = gc.load(gc.make(root, 5, "small", "small"))
    c["test_cmd"] = f"{sys.executable} -m pytest -q -p no:cacheprovider"
    return root, c


def test_verify_true(repo):
    root, c = case_for(repo)
    assert gc.verify(root, c) == {"base_fails": True, "merge_passes": True}


def test_verify_vacuous(repo):
    root, c = case_for(repo)
    c["hidden_tests"] = [{"path": "tests/test_v.py", "text": "def test_v():\n    assert True\n"}]
    assert gc.verify(root, c)["base_fails"] is False


def test_cli_verify_exit(repo, monkeypatch, capsys):
    root, c = case_for(repo)
    monkeypatch.setattr(gc, "verify", lambda r, case: {"base_fails": False, "merge_passes": True})
    assert gc.main(["--root", str(root), "verify"]) == 1
    monkeypatch.setattr(gc, "verify", lambda r, case: {"base_fails": True, "merge_passes": True})
    assert gc.main(["--root", str(root), "verify"]) == 0


def test_private_text_refused(repo, monkeypatch):
    root, base, merge = repo
    real = gc._run

    def run(cmd, cwd=None, timeout=None):
        if cmd[0] == "gh" and cmd[1] == "issue":
            return 0, json.dumps({"title": "T7", "body": "see /Users/someone/private/notes.md"})
        return real(cmd, cwd, timeout) if cmd[0] != "gh" else (0, json.dumps({"mergeCommit": {"oid": merge}, "title": "t", "closingIssuesReferences": [{"number": 7}]}))
    monkeypatch.setattr(gc, "_run", run)
    with pytest.raises(gc.CaseError, match="home path"):
        gc.make(root, 1, "priv", "small")
    assert not (root / "bench" / "golden" / "priv").exists()


@pytest.mark.parametrize("text,kind", [("host my-mac.local", "hostname"), ("ghp_" + "a" * 25, "token"), ("/home/bob/x", "home path")])
def test_load_refuses_private(tmp_path, text, kind):
    d = tmp_path / "x"
    d.mkdir()
    case = {"id": "x", "size": "small", "topic": "golden-x", "base": "b", "merge": "m", "test_cmd": "t", "issues": [{"number": 1, "title": "t", "body": text}], "hidden_tests": []}
    (d / "case.json").write_text(json.dumps(case))
    with pytest.raises(gc.CaseError, match=kind):
        gc.load(d)


def test_private_text_no_false_positive():
    assert gc.private_text({"issues": [], "hidden_tests": [{"text": "Path.home(); threading.local(); self.local"}]}) is None


@pytest.mark.parametrize("over", [{"issues": [{"number": "../../x", "title": "t", "body": "b"}]},
                                  {"issues": [{"number": True, "title": "t", "body": "b"}]},
                                  {"issues": [{"number": 1, "title": "t"}]},
                                  {"issues": ["x"]}])
def test_load_refuses_bad_issue(tmp_path, over):
    with pytest.raises(gc.CaseError, match="issue"):
        gc.load(put(tmp_path, "small", **over))


def test_load_requires_topic(tmp_path):
    d = put(tmp_path, "small"); j = json.loads((d / "case.json").read_text()); del j["topic"]
    (d / "case.json").write_text(json.dumps(j))
    with pytest.raises(gc.CaseError, match="topic"):
        gc.load(d)


def test_verify_merge_with_skipped_test_fails(repo, monkeypatch):
    root, c = case_for(repo)
    real = gc._run
    monkeypatch.setattr(gc, "_run", lambda cmd, cwd=None, timeout=None: (0, "2 passed, 1 skipped in 1s") if "pytest" in cmd else real(cmd, cwd=cwd, timeout=timeout))
    assert gc.verify(root, c)["merge_passes"] is False
