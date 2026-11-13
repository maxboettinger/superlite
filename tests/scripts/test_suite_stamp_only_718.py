"""A suite-narrowed iOS stamp (only=) does not count for maxapp test --ios (#718)."""
import sys
from test_plan_tools import SCRIPTS
from test_suite_stamp_639 import commit, git, repo_with, stamp, tree
sys.path.insert(0, str(SCRIPTS))
import suite_stamp as ss  # noqa: E402


def only_stamp(repo, rev="HEAD", only="App/SuiteA,App/SuiteB"):
    t = tree(repo, rev)
    return stamp(repo, rev, platform="iOS", text=f"tree={t}\nplatform=iOS\ncommit={git(repo, 'rev-parse', rev)}\n"
                                                 f"tests=5\nonly={only}\n")


def test_ios_rejects_only_stamp(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    only_stamp(r)
    assert ss.green_base(r, "maxapp test --ios", []) is None


def test_ios_rejects_empty_only(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    only_stamp(r, only="")
    assert ss.green_base(r, "maxapp test --ios", []) is None


def test_ios_whole_stamp_hits(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    stamp(r, platform="iOS", tests="5")
    out = ss.green_base(r, "maxapp test --ios", [])
    assert out["tests"] == 17 and out["platforms"] == ["macOS", "iOS"]


def test_plain_test_keeps_its_stamp(tmp_path):
    r = repo_with(tmp_path)
    f = stamp(r)
    only_stamp(r)
    out = ss.green_base(r, "maxapp test", [])
    assert out["tests"] == 12 and out["platforms"] == ["macOS"] and out["stamps"] == [str(f)]


def test_ios_only_stamp_on_ancestor_is_no_hit(tmp_path):
    r = repo_with(tmp_path)
    stamp(r)
    only_stamp(r)
    commit(r, {"docs/x.md": "b\n"}, "docs")
    assert ss.green_base(r, "maxapp test --ios", ["docs/**"]) is None


def test_read_stamp_whole_flag(tmp_path):
    r = repo_with(tmp_path)
    f = only_stamp(r)
    assert ss._read_stamp(f, tree(r), "iOS") == 5
    assert ss._read_stamp(f, tree(r), "iOS", whole=True) is None
