# tests/scripts/test_suite_stamp_test_full_720.py
"""Plain maxapp test follows the .maxapp test_full: an iOS part there needs the iOS stamp, narrowed to the same suites (#720)."""
import sys
import pytest
from test_plan_tools import SCRIPTS
from test_suite_stamp_639 import commit, git, repo_with, stamp, tree
sys.path.insert(0, str(SCRIPTS))
import suite_stamp as ss  # noqa: E402


def project(tmp_path, test_full=None, extra=""):
    tmp_path.mkdir(parents=True, exist_ok=True)
    body = "package=Pkg\npackage_scheme=Pkg\nplatforms=macOS iOS\n" + extra
    if test_full is not None:
        body += f"test_full={test_full}\n"
    return repo_with(tmp_path, {"src/a.py": "1\n", "docs/x.md": "a\n", ".maxapp": body})


def ios_stamp(repo, only=None, tests="5", rev="HEAD"):
    t = tree(repo, rev)
    text = f"tree={t}\nplatform=iOS\ncommit={git(repo, 'rev-parse', rev)}\ntests={tests}\n"
    if only is not None:
        text += f"only={only}\n"
    return stamp(repo, rev, platform="iOS", text=text)


def test_whole_ios_needs_the_ios_stamp(tmp_path):
    r = project(tmp_path, "lint macOS iOS")
    stamp(r)
    assert ss.green_base(r, "maxapp test", []) is None


def test_whole_ios_hits_with_both_stamps(tmp_path):
    r = project(tmp_path, "lint macOS iOS")
    m = stamp(r)
    f = ios_stamp(r)
    out = ss.green_base(r, "maxapp test", [])
    assert out["tests"] == 17 and out["platforms"] == ["macOS", "iOS"] and out["stamps"] == [str(m), str(f)]


def test_whole_ios_rejects_a_narrowed_stamp(tmp_path):
    r = project(tmp_path, "macOS iOS")
    stamp(r)
    ios_stamp(r, only="App/SuiteA")
    assert ss.green_base(r, "maxapp test", []) is None


def test_narrowed_ios_hits_with_the_same_suites(tmp_path):
    r = project(tmp_path, "macOS iOS=App/SuiteA,App/SuiteB lint")
    stamp(r)
    ios_stamp(r, only="App/SuiteA,App/SuiteB")
    out = ss.green_base(r, "maxapp test", [])
    assert out["tests"] == 17 and out["platforms"] == ["macOS", "iOS"]


def test_narrowed_ios_ignores_suite_order(tmp_path):
    r = project(tmp_path, "macOS iOS=App/SuiteA,App/SuiteB")
    stamp(r)
    ios_stamp(r, only="App/SuiteB,App/SuiteA")
    assert ss.green_base(r, "maxapp test", [])["tests"] == 17


@pytest.mark.parametrize("only", [None, "", "App/SuiteA", "App/SuiteA,App/SuiteB,App/SuiteC"])
def test_narrowed_ios_needs_equal_suites(tmp_path, only):
    r = project(tmp_path, "macOS iOS=App/SuiteA,App/SuiteB")
    stamp(r)
    ios_stamp(r, only=only)
    assert ss.green_base(r, "maxapp test", []) is None


def test_narrowed_ios_needs_the_ios_stamp(tmp_path):
    r = project(tmp_path, "macOS iOS=App/SuiteA")
    stamp(r)
    assert ss.green_base(r, "maxapp test", []) is None


@pytest.mark.parametrize("test_full", [None, "", "macOS", "lint macOS", "macOS lint"])
def test_macos_only_definition_keeps_the_macos_stamp(tmp_path, test_full):
    r = project(tmp_path, test_full)
    f = stamp(r)
    out = ss.green_base(r, "maxapp test", [])
    assert out["tests"] == 12 and out["platforms"] == ["macOS"] and out["stamps"] == [str(f)]


@pytest.mark.parametrize("test_full", ["iOS", "lint", "macOS iOS=", "macOS iOS=,A/B", "macOS iOS=A/B,", "macOS iOS=A/B,,C/D",
                                       "macOS iOS iOS=A/B", "macOS macOS iOS", "macOS ios", "macOS watchOS",
                                       "'macOS iOS'", '"macOS iOS"'])
def test_malformed_definition_is_no_hit(tmp_path, test_full):
    r = project(tmp_path, test_full)
    stamp(r)
    ios_stamp(r)
    assert ss.green_base(r, "maxapp test", []) is None


def test_duplicate_test_full_key_is_no_hit(tmp_path):
    r = project(tmp_path, "macOS", extra="test_full=macOS iOS\n")
    stamp(r)
    ios_stamp(r)
    assert ss.green_base(r, "maxapp test", []) is None


def test_definition_is_read_like_maxapp(tmp_path):
    r = repo_with(tmp_path, {"src/a.py": "1\n", ".maxapp": "# test_full=macOS\n\n  test_full =   macOS   iOS=App/SuiteA  \npackage=Pkg\n"})
    stamp(r)
    assert ss.green_base(r, "maxapp test", []) is None
    ios_stamp(r, only="App/SuiteA")
    assert ss.green_base(r, "maxapp test", [])["platforms"] == ["macOS", "iOS"]


def test_commented_definition_is_ignored(tmp_path):
    r = repo_with(tmp_path, {"src/a.py": "1\n", ".maxapp": "# test_full=macOS iOS\npackage=Pkg\n"})
    f = stamp(r)
    assert ss.green_base(r, "maxapp test", [])["stamps"] == [str(f)]


def test_definition_is_read_at_the_git_top(tmp_path):
    r = project(tmp_path, "macOS iOS")
    stamp(r)
    assert ss.green_base(r / "src", "maxapp test", []) is None
    ios_stamp(r)
    assert ss.green_base(r / "src", "maxapp test", [])["tests"] == 17


def test_ancestor_base_needs_the_ios_stamp_too(tmp_path):
    r = project(tmp_path, "macOS iOS")
    stamp(r)
    commit(r, {"docs/x.md": "b\n"}, "docs")
    assert ss.green_base(r, "maxapp test", ["docs/**"]) is None
    ios_stamp(r, rev="HEAD~1")
    out = ss.green_base(r, "maxapp test", ["docs/**"])
    assert out["tests"] == 17 and out["changed"] == ["docs/x.md"]


def test_ios_flag_keeps_the_whole_suite_rule(tmp_path):
    r = project(tmp_path, "macOS iOS=App/SuiteA")
    stamp(r)
    ios_stamp(r, only="App/SuiteA")
    assert ss.green_base(r, "maxapp test --ios", []) is None
    ios_stamp(r)
    assert ss.green_base(r, "maxapp test --ios", [])["tests"] == 17


def test_maxapp_platforms_unchanged():
    assert ss.maxapp_platforms("maxapp test") == ["macOS"]
    assert ss.maxapp_platforms("maxapp test --ios") == ["macOS", "iOS"]
    assert ss.maxapp_platforms("maxapp test --only A/B") is None


def test_test_full_ios_values(tmp_path):
    assert ss.test_full_ios(project(tmp_path / "a", "macOS lint")) is None
    assert ss.test_full_ios(project(tmp_path / "b", "macOS iOS")) == frozenset()
    assert ss.test_full_ios(project(tmp_path / "c", "macOS iOS=A/B,C/D")) == frozenset({"A/B", "C/D"})
    assert ss.test_full_ios(project(tmp_path / "d")) is None
    e = tmp_path / "e"
    e.mkdir()
    assert ss.test_full_ios(repo_with(e)) is None
    with pytest.raises(ValueError):
        ss.test_full_ios(project(tmp_path / "f", "iOS"))


def test_read_stamp_suites(tmp_path):
    r = project(tmp_path, "macOS iOS=A/B,C/D")
    f = ios_stamp(r, only="C/D,A/B")
    assert ss._read_stamp(f, tree(r), "iOS", suites=frozenset({"A/B", "C/D"})) == 5
    assert ss._read_stamp(f, tree(r), "iOS", suites=frozenset({"A/B"})) is None
    g = ios_stamp(r)
    assert ss._read_stamp(g, tree(r), "iOS", suites=frozenset({"A/B", "C/D"})) is None
    assert ss._read_stamp(g, tree(r), "iOS") == 5
