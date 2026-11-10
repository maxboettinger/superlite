"""sl backlog plan remembers its source, takes --github and --max-batches, and passes the carry dict (#473, #452)."""
import pytest

from test_backlog_cli import bk, cli, load, BATCH, bl, bs  # noqa: F401  bk is the CLI fixture
from test_backlog_jira_208 import jk, JB, ACLI  # noqa: F401  jk is the acli fixture

NO_SOURCE = ('BLOCKED: no backlog source remembered and AGENTS.md or CLAUDE.md names Jira; run sl backlog plan --jql "<query>" '
             'for Jira issues or --github for GitHub issues (--issues pins single issues); a plain plan then reuses the choice')
NO_JQL = ('BLOCKED: the last plan read Jira issues by key and remembers no JQL; run sl backlog plan --jql "<query>", '
          '--issues KEYS or --github')
LINE = 'source: Jira --jql "project = PIX" (remembered from the last plan; --github, --jql or --issues picks another)'


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


def source(ns):
    return load(ns).get("source")


def test_jql_remembered_and_reused(jk, capsys):
    assert cli(capsys, "plan", "--jql", "project = PIX")[0] == 0
    assert source(jk) == {"tracker": "jira", "jql": "project = PIX"}
    jk.acli.clear()
    jk.gh.clear()
    rc, out = cli(capsys, "plan", "--reset")
    assert rc == 0 and out.splitlines()[0] == LINE
    assert jk.acli[0][jk.acli[0].index("--jql") + 1] == "project = PIX"
    assert not any(g[:1] == ["api"] for g in jk.gh)


def test_github_remembered_no_line(bk, capsys):
    rc, out = cli(capsys, "plan")
    assert rc == 0 and source(bk) == {"tracker": "github"} and "source:" not in out


def test_agents_md_jira_refuses_before_any_call(bk, capsys):
    (bk.root / "AGENTS.md").write_text("Tracker: JIRA project PIX")
    assert cli(capsys, "plan") == (2, NO_SOURCE + "\n")
    assert bk.gh == []
    assert cli(capsys, "plan", "--github")[0] == 0 and source(bk) == {"tracker": "github"}
    assert cli(capsys, "plan", "--reset")[0] == 0


def test_claude_md_checked(bk, capsys):
    (bk.root / "CLAUDE.md").write_text("we use jira here")
    assert cli(capsys, "plan") == (2, NO_SOURCE + "\n")


def test_word_inside_name_not_jira(bk, capsys):
    (bk.root / "AGENTS.md").write_text("see jirafy.py")
    assert cli(capsys, "plan")[0] == 0


def test_key_pin_keeps_jql(jk, capsys):
    assert cli(capsys, "plan", "--jql", "Q")[0] == 0
    jk.batches = [{**JB, "issues": ["PIX-1"]}]
    jk.ret = [ACLI[0]]
    assert cli(capsys, "plan", "--reset", "--issues", "PIX-1")[0] == 0
    assert source(jk) == {"tracker": "jira", "jql": "Q"}


def test_key_pin_without_jql_then_plain_refused(jk, capsys):
    jk.batches = [{**JB, "issues": ["PIX-1"]}]
    jk.ret = [ACLI[0]]
    assert cli(capsys, "plan", "--issues", "PIX-1")[0] == 0
    assert source(jk) == {"tracker": "jira"}
    assert cli(capsys, "plan", "--reset") == (2, NO_JQL + "\n")


def test_github_excludes_jql(bk, capsys):
    with pytest.raises(SystemExit) as e:
        cli(capsys, "plan", "--github", "--jql", "x")
    assert e.value.code == 2


@pytest.mark.parametrize("n", ["0", "21"])
def test_max_batches_bounds(bk, capsys, n):
    assert cli(capsys, "plan", "--max-batches", n) == (2, "BLOCKED: --max-batches: 1 to 20\n")
    assert bk.gh == []


def test_max_batches_sets_cap(bk, capsys):
    bk.vis = "PRIVATE"
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--max-batches", "1")[0] == 0
    d = load(bk)
    assert [o["reason"] for o in d["outside"] if o["number"] == 2] == ["not planned (cap)"]
    assert d["max_batches"] == 1 and bk.ctx["max_batches"] == 1


def test_rejected_plan_keeps_source(jk, capsys):
    assert cli(capsys, "plan", "--jql", "Q")[0] == 0
    jk.batches = []
    assert cli(capsys, "plan", "--reset", "--github")[0] == 3
    assert source(jk) == {"tracker": "jira", "jql": "Q"}


def test_carry_always_passed(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    assert bk.ctx["carry"] == {}
