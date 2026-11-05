import sys, types
from backlog_fixtures import Q  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog as bl  # noqa: E402


def _run(monkeypatch, tmp_path, assoc):
    seen, briefs = [], []
    rows = [{"number": n, "title": f"T{n}", "author": {"login": "x"}, "authorAssociation": a} for n, a in enumerate(assoc, 1)]
    def gh(args):
        seen.append(args)
        return {"nameWithOwner": "o/r", "visibility": "PUBLIC"} if args[:2] == ["repo", "view"] else rows
    def triage(sd, root, trusted, repo, tier, tmo):
        briefs.extend(t["number"] for t in trusted)
        return None, ["BLOCKED: stop"]
    (tmp_path / ".superlite").mkdir()
    monkeypatch.setattr(bl, "_root", lambda: tmp_path)
    monkeypatch.setattr(bl, "_gh", gh)
    monkeypatch.setattr(bl, "_triage", triage)
    bl.cmd_plan(types.SimpleNamespace(reset=False, tier=1, timeout_min=1))
    return seen, briefs


def test_issue_list_uses_rest_and_gate_holds(monkeypatch, tmp_path):
    seen, briefs = _run(monkeypatch, tmp_path, ["OWNER", "MEMBER", "COLLABORATOR", "NONE"])
    call = next(a for a in seen if a[0] in ("api", "issue"))
    assert call[0] == "api" and "--json" not in call
    assert not any("authorAssociation" in x and a[0] == "issue" for a in seen for x in a)
    assert briefs == [1, 2, 3]


def test_jq_maps_fields_and_drops_prs():
    assert "pull_request" in bl.ISSUES_JQ and "author_association" in bl.ISSUES_JQ
