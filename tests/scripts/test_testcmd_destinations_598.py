"""#598: destination rewrite, platforms and result merge helpers in testcmd."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

IOS = "xcodebuild test -scheme A -destination 'platform=iOS Simulator,name=iPhone 16'"


def part(**kw):
    base = {"passed": 0, "failed": 0, "skipped": 0, "names": [], "tail": [], "empty": "", "counted": True, "error": "", "marker": ""}
    base.update(kw)
    return base


def test_with_destination_replaces_single_quoted():
    assert testcmd.with_destination(IOS, "platform=macOS") == "xcodebuild test -scheme A -destination platform=macOS"


def test_with_destination_appends_before_pipe():
    out = testcmd.with_destination("xcodebuild test -scheme A | xcpretty", "platform=iOS Simulator,name=X")
    assert out == "xcodebuild test -scheme A -destination 'platform=iOS Simulator,name=X' | xcpretty"


def test_with_destination_none_without_xcodebuild():
    assert testcmd.with_destination("swift test", "platform=macOS") is None


def test_destination_value_quoted_both_ways():
    dq = 'xcodebuild test -destination "platform=iOS Simulator,name=X" -scheme A'
    assert testcmd.with_destination(dq, "platform=macOS") == "xcodebuild test -scheme A -destination platform=macOS"
    bare = "xcodebuild test -destination platform=macOS -scheme A"
    out = testcmd.with_destination(bare, "platform=tvOS Simulator,name=T")
    assert out == "xcodebuild test -scheme A -destination 'platform=tvOS Simulator,name=T'"
    assert out.count("-destination") == 1


def test_with_destination_each_segment():
    out = testcmd.with_destination("xcodebuild build -scheme A && xcodebuild test -scheme A", "platform=macOS")
    assert out == "xcodebuild build -scheme A -destination platform=macOS && xcodebuild test -scheme A -destination platform=macOS"


def test_destination_platform():
    assert testcmd.destination_platform("platform=iOS Simulator,name=iPhone 16") == "iOS"
    assert testcmd.destination_platform("generic/platform=macOS") == "macOS"
    assert testcmd.destination_platform("platform=macOS,variant=Mac Catalyst") == "macCatalyst"
    assert testcmd.destination_platform("id=00008030-ABC") is None


def test_command_platforms():
    assert testcmd.command_platforms("swift test") == ["macOS"]
    assert testcmd.command_platforms(IOS) == ["iOS"]
    assert testcmd.command_platforms("npm test") == []


def test_declared_platforms(tmp_path):
    (tmp_path / "Package.swift").write_text("let p = Package(name: \"A\", platforms: [.iOS(.v17), .macOS(.v14)])\n", encoding="utf-8")
    sub = tmp_path / "Sub" / "Inner"
    sub.mkdir(parents=True)
    (sub / "Package.swift").write_text("let p = Package(name: \"B\", platforms: [.watchOS(.v10)])\n", encoding="utf-8")
    assert testcmd.declared_platforms(tmp_path) == ["iOS", "macOS", "watchOS"]


def test_declared_platforms_none(tmp_path):
    (tmp_path / "Package.swift").write_text("let p = Package(name: \"A\")\n", encoding="utf-8")
    assert testcmd.declared_platforms(tmp_path) == []


def test_platforms_in_comment_ignored(tmp_path):
    (tmp_path / "Package.swift").write_text("// platforms: [.tvOS(.v17)]\nlet p = Package(name: \"A\")\n", encoding="utf-8")
    assert testcmd.declared_platforms(tmp_path) == []


def test_merge_parsed():
    ok = part(passed=3, tail=["ok"], marker="** TEST SUCCEEDED **")
    bad = part(passed=2, failed=1, skipped=1, names=["ParserTests/parses()"], tail=["bad"], marker="** TEST FAILED **")
    got = testcmd.merge_parsed([("platform=macOS", ok), ("platform=iOS Simulator,name=X", bad)])
    assert got == part(passed=5, failed=1, skipped=1, names=["ParserTests/parses()"], tail=["bad"], marker="** TEST FAILED **")


def test_merge_parsed_error_prefixed():
    got = testcmd.merge_parsed([("platform=macOS", part(error="a.swift:3:1: error: x"))])
    assert got["error"] == "[platform=macOS] a.swift:3:1: error: x"


def test_merge_parsed_empty_when_nothing_counted():
    got = testcmd.merge_parsed([("a", part(counted=False, empty="no tests ran")), ("b", part(counted=False))])
    assert got["empty"] == "no tests ran" and got["counted"] is False


def test_resolve_carries_destinations(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": "echo hi", "destinations": ["platform=macOS", "", 3]}), encoding="utf-8")
    assert testcmd.resolve(tmp_path)["destinations"] == ["platform=macOS"]
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": "pytest"}), encoding="utf-8")
    assert testcmd.resolve(tmp_path)["destinations"] == []


def test_invalid_destinations_ignored(tmp_path, capsys):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": "echo hi", "destinations": "platform=macOS"}), encoding="utf-8")
    assert testcmd.resolve(tmp_path)["destinations"] == []
    assert 'must be a list of xcodebuild destination strings' in capsys.readouterr().err


def test_with_destination_keeps_redirects_whole():
    out = testcmd.with_destination("xcodebuild test -scheme A 2>&1 | xcpretty", "platform=macOS")
    assert out == "xcodebuild test -scheme A -destination platform=macOS 2>&1 | xcpretty" or out == "xcodebuild test -scheme A 2>&1 -destination platform=macOS | xcpretty"
    assert "2> -destination" not in out and "&1" in out and "2>&1" in out
    both = testcmd.with_destination("xcodebuild test -scheme A &> out.log", "platform=macOS")
    assert "&> out.log" in both and both.count("-destination") == 1
