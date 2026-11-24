"""The parser capture reads each tool's real argparse tree, follows routed subcommands, leaves the repo alone."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import doc_contract_parsers as dcp  # noqa: E402

REPO = HERE.parents[1]
# real subparsers with positionals only (or no arguments): no flag, not a routing placeholder
NO_ARGS = {("backlog", "skip"), ("backlog", "note"), ("backlog", "unskip"), ("experiment", "show"), ("experiment", "clear"), ("history", "import"), ("golden_case", "verify"), ("golden_case", "list")}


def _tools():
    return dcp.parser_trees()["tools"]


def test_flat_and_sub_parsers():
    t = _tools()
    assert {"--reset", "--add", "--github", "--max-batches", "--issues", "--jql", "--proposal"} <= set(t["backlog"]["subs"]["plan"]["flags"])
    assert {"--accounts", "--plan", "--config"} <= set(t["fleet"]["subs"]["on"]["flags"])


def test_routed_subcommands_follow_the_route():
    t = _tools()
    assert {"--wave", "--timeout"} <= set(t["fleet"]["subs"]["wait"]["flags"])
    assert {"--layer", "--plan"} <= set(t["fleet"]["subs"]["run"]["flags"])
    ship = t["backlog"]["subs"]["ship"]
    assert {"--wait", "--version", "--title"} <= set(ship["flags"])
    assert t["backlog"]["subs"]["notes"] == ship
    assert {"--plan", "--base"} <= set(t["plan_tools"]["subs"]["packet"]["flags"])
    assert {"--note", "--cap"} <= set(t["backlog"]["subs"]["start"]["flags"])


def _walk(node, path=()):
    yield path, node
    for name, sub in node["subs"].items():
        yield from _walk(sub, path + (name,))


def test_choices_are_read():
    t = _tools()
    assert "--wait" not in t["backlog"]["subs"]["ship"]["choices"]
    found = [(n, p) for n, tree in t.items() if tree for p, node in _walk(tree) if node["choices"]]
    assert found, "no flag with choices anywhere in the tree"
    # incident add --kind and plan_tools taskgraph --format have fixed choices
    assert t["incident"]["subs"]["add"]["choices"]["--kind"][:2] == ["test-failure", "exception"]
    assert "verified" in t["incident"]["subs"]["add"]["choices"]["--kind"]
    assert t["plan_tools"]["subs"]["taskgraph"]["choices"]["--format"] == ["graph", "full"]


def test_no_placeholder_left_unrouted():
    for name, tree in _tools().items():
        if not tree:
            continue
        for path, node in _walk(tree):
            if len(path) == 1 and set(node["flags"]) <= {"-h", "--help"} and not node["subs"]:
                key = (name, path[0])
                assert key in dcp.ROUTES or key in NO_ARGS, f"placeholder left unrouted: {key}"


def test_hand_parsed_and_libraries():
    t = _tools()
    for name in ("trees", "render_edit", "autocommit"):
        assert t[name] is None
    assert t.get("fleet_state") is None and t.get("guard_tools") is None
    assert not [k for k in t if k.startswith("_")]
    assert t["version"] == {"flags": [], "choices": {}, "subs": {}}


def test_no_capture_errors():
    assert dcp.parser_trees()["errors"] == {}


def _status():
    return subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True,
                          env={k: v for k, v in __import__("os").environ.items()
                               if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}).stdout


def test_capture_leaves_the_repo_alone():
    before = _status()
    dcp.capture_uncached()
    assert _status() == before
