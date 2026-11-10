"""testcmd owns the one Swift -only-testing mapping: target membership from the Xcode project and Package.swift paths (#431)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

PBX = """// !$*UTF8*$!
{
    archiveVersion = 1;
    classes = {
    };
    objectVersion = 77;
    objects = {

/* Begin PBXBuildFile section */
        C1 /* FooTests.swift in Sources */ = {isa = PBXBuildFile; fileRef = F1 /* FooTests.swift */; };
        C2 /* ContentView.swift in Sources */ = {isa = PBXBuildFile; fileRef = F2 /* ContentView.swift */; };
        C3 /* Shared.swift in Sources */ = {isa = PBXBuildFile; fileRef = F3 /* Shared.swift */; };
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
        F1 /* FooTests.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = FooTests.swift; sourceTree = "<group>"; };
        F2 /* ContentView.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = ContentView.swift; sourceTree = "<group>"; };
        F3 /* Shared.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = Support/Shared.swift; sourceTree = SOURCE_ROOT; };
        F4 /* App.app */ = {isa = PBXFileReference; explicitFileType = wrapper.application; path = App.app; sourceTree = BUILT_PRODUCTS_DIR; };
/* End PBXFileReference section */

/* Begin PBXFileSystemSynchronizedRootGroup section */
        S1 /* Snapshots */ = {isa = PBXFileSystemSynchronizedRootGroup; path = Snapshots; sourceTree = "<group>"; };
/* End PBXFileSystemSynchronizedRootGroup section */

/* Begin PBXGroup section */
        G0 = {
            isa = PBXGroup;
            children = (
                G1 /* App */,
                G2 /* Tests */,
            );
            sourceTree = "<group>";
        };
        G1 /* App */ = {
            isa = PBXGroup;
            children = (
                F2 /* ContentView.swift */,
            );
            path = App;
            sourceTree = "<group>";
        };
        G2 /* Tests */ = {
            isa = PBXGroup;
            children = (
                G3 /* Unit Tests */,
                S1 /* Snapshots */,
            );
            path = Tests;
            sourceTree = "<group>";
        };
        G3 /* Unit Tests */ = {
            isa = PBXGroup;
            children = (
                F1 /* FooTests.swift */,
            );
            name = "Unit Tests";
            path = Unit;
            sourceTree = "<group>";
        };
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
        A1 /* App */ = {
            isa = PBXNativeTarget;
            buildPhases = (
                B1 /* Sources */,
            );
            name = App;
            productReference = F4 /* App.app */;
            productType = "com.apple.product-type.application";
        };
        A2 /* AppTests */ = {
            isa = PBXNativeTarget;
            buildPhases = (
                B2 /* Sources */,
            );
            name = AppTests;
            productType = "com.apple.product-type.bundle.unit-test";
        };
        A3 /* App SnapshotTests */ = {
            isa = PBXNativeTarget;
            buildPhases = (
                B3 /* Sources */,
            );
            fileSystemSynchronizedGroups = (
                S1 /* Snapshots */,
            );
            name = "App SnapshotTests";
            productType = "com.apple.product-type.bundle.unit-test";
        };
/* End PBXNativeTarget section */

/* Begin PBXProject section */
        P0 /* Project object */ = {
            isa = PBXProject;
            mainGroup = G0;
            projectDirPath = "";
            projectRoot = "";
            targets = (
                A1 /* App */,
                A2 /* AppTests */,
                A3 /* App SnapshotTests */,
            );
        };
/* End PBXProject section */

/* Begin PBXSourcesBuildPhase section */
        B1 /* Sources */ = {isa = PBXSourcesBuildPhase; files = (C2 /* ContentView.swift in Sources */, ); };
        B2 /* Sources */ = {isa = PBXSourcesBuildPhase; files = (C1 /* FooTests.swift in Sources */, C3 /* Shared.swift in Sources */, ); };
        B3 /* Sources */ = {isa = PBXSourcesBuildPhase; files = ( ); };
/* End PBXSourcesBuildPhase section */
    };
    rootObject = P0 /* Project object */;
}
"""
SUITE = "import XCTest\nfinal class {0}: XCTestCase {{\n    func testA() {{}}\n}}\n"
FILES = {
    "Tests/Unit/FooTests.swift": SUITE.format("FooTests"),
    "Tests/Unit/NewTests.swift": SUITE.format("NewTests"),
    "Tests/Snapshots/Views/CardTests.swift": SUITE.format("CardTests"),
    "App/ContentView.swift": "struct ContentView {}\n",
    "App/Model.swift": "struct Model {}\n",
    "Support/Shared.swift": "func shared() -> Int { 1 }\n",
}
CYCLE = ('{ objects = { G9 = { isa = PBXGroup; children = ( ); sourceTree = "<group>"; }; '
         'G0 = { isa = PBXGroup; children = ( G1 ); path = a; sourceTree = "<group>"; }; '
         'G1 = { isa = PBXGroup; children = ( G0, F1 ); path = b; sourceTree = "<group>"; }; '
         'F1 = { isa = PBXFileReference; path = X.swift; sourceTree = "<group>"; }; '
         'C1 = { isa = PBXBuildFile; fileRef = F1; }; B1 = { isa = PBXSourcesBuildPhase; files = ( C1 ); }; '
         'A1 = { isa = PBXNativeTarget; name = T; buildPhases = ( B1 ); productType = "com.apple.product-type.bundle.unit-test"; }; '
         'P0 = { isa = PBXProject; mainGroup = G9; }; }; rootObject = P0; }')


def project(root, sub=""):
    base = root / sub if sub else root
    (base / "App.xcodeproj").mkdir(parents=True)
    (base / "App.xcodeproj" / "project.pbxproj").write_text(PBX, encoding="utf-8")
    for rel, text in FILES.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")
    return root


def config(root, cfg):
    (root / ".superlite").mkdir(exist_ok=True)
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")


def test_parse_plist_values():
    got = testcmd.parse_plist('// !$*UTF8*$!\n{ a = 1; b = "x \\"y\\""; /* c */ c = ( p, "q r", ); '
                              'd = { e = <0fbd>; }; f = Sources/App.swift; }')
    assert got == {"a": "1", "b": 'x "y"', "c": ["p", "q r"], "d": {"e": "<0fbd>"}, "f": "Sources/App.swift"}


@pytest.mark.parametrize("text", ["{ a = 1; ", "{ a = ( 1, 2 ; }", "<<<<<<< HEAD\n{ a = 1; }", "{ a 1; }",
                                  '{ a = "open; }', "{ a = 1; } x", "{ a = 1; /* never closed }"])
def test_parse_plist_malformed_raises(text):
    with pytest.raises(ValueError):
        testcmd.parse_plist(text)


def test_membership_from_pbxproj(tmp_path):
    m = testcmd.swift_target_map(project(tmp_path))
    assert m["tests"] == {"AppTests", "App SnapshotTests"}
    assert m["files"]["Tests/Unit/FooTests.swift"] == {"AppTests"}
    assert m["files"]["Support/Shared.swift"] == {"AppTests"}
    assert m["files"]["App/ContentView.swift"] == {"App"}
    assert m["dirs"]["Tests/Snapshots"] == {"App SnapshotTests"}
    assert m["dirs"]["Tests/Unit"] == {"AppTests"}
    assert m["dirs"]["App"] == {"App"}
    assert "App.app" not in m["files"]


@pytest.mark.parametrize("rel,want", [
    ("Tests/Unit/FooTests.swift", "AppTests"),
    ("Tests/Unit/NewTests.swift", "AppTests"),
    ("Tests/Unit/Helpers/Fake.swift", "AppTests"),
    ("Tests/Snapshots/Views/CardTests.swift", "App SnapshotTests"),
    ("Support/Shared.swift", "AppTests"),
    ("App/ContentView.swift", None),
    ("App/Model.swift", None),
    ("Docs/Readme.swift", None),
])
def test_owning_test_target_by_membership(tmp_path, rel, want):
    m = testcmd.swift_target_map(project(tmp_path))
    assert testcmd.owning_test_target(rel, m["tests"], m) == want


def test_owning_without_members_keeps_folder_rule():
    assert testcmd.owning_test_target("AppTests/FooTests.swift", {"AppTests"}) == "AppTests"
    assert testcmd.owning_test_target("Tests/Unit/FooTests.swift", {"AppTests"}) is None
    assert testcmd.owning_test_target("Tests/CoreTests/BarTests.swift", set()) == "CoreTests"


def test_only_testing_maps_member_files(tmp_path):
    root = project(tmp_path)
    assert testcmd.only_testing(["Tests/Unit/FooTests.swift", "Tests/Snapshots/Views/CardTests.swift"], root) == (
        "-only-testing:AppTests/FooTests '-only-testing:App SnapshotTests/CardTests'")


def test_only_testing_source_path_is_none_with_note(tmp_path):
    root = project(tmp_path)
    notes = []
    assert testcmd.only_testing(["Tests/Unit/FooTests.swift", "App/ContentView.swift"], root, notes) is None
    assert notes == ["App/ContentView.swift is not in a test target; running the unfiltered test command"]


def test_only_testing_helper_runs_its_target(tmp_path):
    root = project(tmp_path)
    notes = []
    assert testcmd.only_testing(["Support/Shared.swift"], root, notes) == "-only-testing:AppTests"
    assert notes == ["Support/Shared.swift declares no test suite; using -only-testing:AppTests"]


def test_only_testing_prints_notes_without_a_list(tmp_path, capsys):
    root = project(tmp_path)
    assert testcmd.only_testing(["App/Model.swift"], root) is None
    assert capsys.readouterr().err == "testcmd: App/Model.swift is not in a test target; running the unfiltered test command\n"


def test_only_testing_empty_paths():
    assert testcmd.only_testing([]) == ""


def test_only_testing_quotes_free_function(tmp_path):
    f = tmp_path / "Tests" / "KitTests" / "FreeTests.swift"
    f.parent.mkdir(parents=True)
    f.write_text("import Testing\n@Test func adds() {}\n", encoding="utf-8")
    assert testcmd.only_testing(["Tests/KitTests/FreeTests.swift"], tmp_path) == "'-only-testing:KitTests/adds()'"


def test_only_testing_target_less_path_is_none(tmp_path):
    (tmp_path / "FooTests.swift").write_text(SUITE.format("FooTests"), encoding="utf-8")
    assert testcmd.only_testing(["FooTests.swift"], tmp_path, []) is None


def test_nested_project_paths_are_root_relative(tmp_path):
    project(tmp_path, "ios")
    m = testcmd.swift_target_map(tmp_path)
    assert testcmd.owning_test_target("ios/Tests/Unit/FooTests.swift", m["tests"], m) == "AppTests"
    assert testcmd.owning_test_target("ios/App/ContentView.swift", m["tests"], m) is None
    assert testcmd.only_testing(["ios/Tests/Unit/FooTests.swift"], tmp_path) == "-only-testing:AppTests/FooTests"


def test_project_search_depth_and_skips(tmp_path):
    project(tmp_path, "apps/ios")
    for skip in (".build/dep", "node_modules/pkg", "Pods/Dep", "DerivedData/Dep", "a/b/c"):
        (tmp_path / skip).mkdir(parents=True)
        (tmp_path / skip / "Package.swift").write_text('.testTarget(name: "DepTests")\n', encoding="utf-8")
    assert testcmd.swift_test_targets(tmp_path) == {"AppTests", "App SnapshotTests"}


def test_package_test_target_path(tmp_path):
    (tmp_path / "Kit").mkdir()
    (tmp_path / "Kit" / "Package.swift").write_text(
        'let package = Package(name: "Kit", targets: [\n'
        '    .target(name: "Kit", path: "Sources/KitCore"),\n'
        '    // .testTarget(name: "OldTests"),\n'
        '    .testTarget(\n        name: "KitTests",\n'
        '        dependencies: ["Kit", .product(name: "Nimble", package: "Nimble")],\n'
        '        path: "Tests/Unit"\n    ),\n'
        '    .testTarget(name: "KitUITests", dependencies: ["Kit"]),\n])\n', encoding="utf-8")
    m = testcmd.swift_target_map(tmp_path)
    assert m["tests"] == {"KitTests", "KitUITests"}
    assert m["dirs"]["Kit/Tests/Unit"] == {"KitTests"}
    assert m["dirs"]["Kit/Tests/KitUITests"] == {"KitUITests"}
    assert testcmd.owning_test_target("Kit/Tests/Unit/ParserTests.swift", m["tests"], m) == "KitTests"


def test_generated_project_ignored_by_git_is_read(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("*.xcodeproj/\n", encoding="utf-8")
    (tmp_path / "project.yml").write_text("name: App\n", encoding="utf-8")
    root = project(tmp_path)
    assert testcmd.only_testing(["Tests/Unit/NewTests.swift"], root) == "-only-testing:AppTests/NewTests"


def test_unparsable_pbxproj_falls_back_to_folders(tmp_path):
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "App.xcodeproj" / "project.pbxproj").write_text("<<<<<<< HEAD\n{\n", encoding="utf-8")
    f = tmp_path / "Tests" / "KitTests" / "FooTests.swift"
    f.parent.mkdir(parents=True)
    f.write_text(SUITE.format("FooTests"), encoding="utf-8")
    assert testcmd.swift_test_targets(tmp_path) == set()
    assert testcmd.only_testing(["Tests/KitTests/FooTests.swift"], tmp_path) == "-only-testing:KitTests/FooTests"


def test_group_cycle_ends(tmp_path):
    (tmp_path / "A.xcodeproj").mkdir()
    (tmp_path / "A.xcodeproj" / "project.pbxproj").write_text(CYCLE, encoding="utf-8")
    m = testcmd.swift_target_map(tmp_path)
    assert m["tests"] == {"T"} and m["files"] == {} and m["dirs"] == {}


def test_resolve_unmapped_runs_unfiltered(tmp_path, capsys):
    root = project(tmp_path)
    config(root, {"language": "swift", "test": "xcodebuild test -scheme App {only_testing}",
                  "test_file": "xcodebuild test -scheme App {only_testing}"})
    assert testcmd.resolve(root, ["App/ContentView.swift"])["command"] == "xcodebuild test -scheme App "
    assert ("testcmd: App/ContentView.swift is not in a test target; running the unfiltered test command"
            in capsys.readouterr().err)
    notes = []
    spec = testcmd.resolve(root, ["Tests/Unit/FooTests.swift"], notes=notes)
    assert spec["command"] == "xcodebuild test -scheme App -only-testing:AppTests/FooTests" and notes == []
    assert capsys.readouterr().err == ""


def test_cli_fast_uses_target_ids(tmp_path):
    root = project(tmp_path)
    config(root, {"language": "swift", "test": "xcodebuild test -scheme App",
                  "test_file": "xcodebuild test -scheme App {only_testing}"})
    r = subprocess.run([sys.executable, str(SCRIPTS / "testcmd.py"), "--root", str(root), "--fast",
                        "Tests/Snapshots/Views/CardTests.swift"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["command"] == "xcodebuild test -scheme App '-only-testing:App SnapshotTests/CardTests'"


def test_dot_slash_and_dotdot_paths_are_normalized(tmp_path):
    (tmp_path / "Package.swift").write_text('.testTarget(name: "KitTests", path: "Spec")\n')
    (tmp_path / "Spec").mkdir()
    (tmp_path / "Spec" / "ATests.swift").write_text("final class ATests: XCTestCase {}\n")
    for p in ("./Spec/ATests.swift", "Spec/../Spec/ATests.swift"):
        assert testcmd.only_testing([p], tmp_path, []) == "-only-testing:KitTests/ATests"
