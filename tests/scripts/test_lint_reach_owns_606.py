"""#601/#596 follow-ups (B146): lint warns on Running-app checks with no way in, symlinked Owns and Also-touches entries."""
import json
import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools as ptm  # noqa: E402

PLAN_TOOLS = SCRIPTS / "plan_tools.py"
FENCE = "```"
GRAPH = f"""{FENCE}mermaid
flowchart LR
  T1[one]
  T2[two]
  T3[three]
  %% taskgraph
  T1 --> T2
{FENCE}
"""
UI = f"""# Plan
**Goal:** x.

{GRAPH}
### T1 inbox view · Complexity 3 · Est. context 30k
**Owns:** App/Views/InboxView.swift

### T2 empty fixture · Complexity 2 · Est. context 30k
**Owns:** App/Fixtures/EmptyInbox.swift

### T3 model · Complexity 2 · Est. context 30k
**Owns:** App/Model/Inbox.swift

## Running-app checks
- C1: iOS simulator; reach: -fixture empty-inbox (T2); see: the empty state text
- C2: iOS simulator; reach: open the inbox; see: three rows
- C3: macOS app; reach: Settings > Accounts; see: the account list
- C4: macOS app; reach: InboxView preview; see: the badge
- C5: web page; reach: http://localhost:3000/inbox; see: rows
- C6: iOS simulator; see: the title
"""
LINKS = f"""# Plan
**Goal:** x.

{GRAPH}
### T1 one · Complexity 2 · Est. context 30k
**Owns:** src/link.py, src/out.py, src/a.py

### T2 two · Complexity 2 · Est. context 30k
**Owns:** src/b.py

### T3 three · Complexity 2 · Est. context 30k
**Owns:** src/c.py
"""
ALSO = LINKS.replace("**Owns:** src/link.py, src/out.py, src/a.py",
                     "**Owns:** src/a.py\n**Also-touches:** src/b.py, src/a.py, src/z.py, src/c.py")
C2 = ('WARNING: REACH: C2 reach "open the inbox" names no launch argument, fixture, URL, UI path, preview or task; '
      "name the way in, or add a task that makes the state reachable and name it (reach: -fixture empty-inbox (T4))")
C3 = ('WARNING: REACH: C3 runs on macos, which test-cmd.json "launch" marks "worker": false, and its reach names no '
      "preview or task; reach it through a preview, or add a task that makes it reachable another way and name it")
C6 = "WARNING: REACH: C6 has no reach: part; name how the checker reaches the state (writing-plans: Reach)"


def proj_with(base, text, launch=None):
    proj = base / "proj"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".git").mkdir()
    if launch is not None:
        cfg = {"language": "swift", "test": "swift test", "launch": launch}
        (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    p = proj / "plan.md"
    p.write_text(text, encoding="utf-8")
    return proj, p


def lint(base, proj, p):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(base / "home"))
    return subprocess.run([sys.executable, str(PLAN_TOOLS), "lint", "--plan", str(p)], capture_output=True, text=True,
                          cwd=proj, env=env, timeout=120).stdout


def test_reach_without_a_way_in_warns(tmp_path):
    proj, p = proj_with(tmp_path, UI)
    assert ptm.reach_warnings(ptm.Plan.load(str(p)), proj) == [C2, C6]


def test_reach_on_a_platform_no_worker_launches(tmp_path):
    launch = {"macos": {"worker": False, "why": "shares the user's container"}, "ios": {"worker": True}}
    proj, p = proj_with(tmp_path, UI, launch)
    assert ptm.reach_warnings(ptm.Plan.load(str(p)), proj) == [C2, C3, C6]


def test_reach_needs_ui_files(tmp_path):
    text = (UI.replace("App/Views/InboxView.swift", "src/inbox.py").replace("App/Fixtures/EmptyInbox.swift", "src/fixture.py")
            .replace("App/Model/Inbox.swift", "src/model.py"))
    proj, p = proj_with(tmp_path, text)
    assert ptm.reach_warnings(ptm.Plan.load(str(p)), proj) == []
    assert ptm.reach_warnings(ptm.Plan.load(str(p)), None) == []


@pytest.mark.parametrize("path, ui", [
    ("App/Views/InboxView.swift", True), ("web/src/Inbox.tsx", True), ("App/Main.storyboard", True),
    ("app/ui/Badge.kt", True), ("App/Model/Inbox.swift", False), ("src/inbox.py", False),
    ("Tests/AppTests/InboxViewTests.swift", False),
])
def test_ui_file(path, ui):
    assert ptm.ui_file(path) is ui


def test_symlinked_owns_name_their_target(tmp_path):
    proj, p = proj_with(tmp_path, LINKS)
    (proj / "src").mkdir()
    (proj / "lib").mkdir()
    (proj / "lib" / "real.py").write_text("R = 0\n", encoding="utf-8")
    (proj / "src" / "a.py").write_text("A = 0\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("O = 0\n", encoding="utf-8")
    try:
        os.symlink("../lib/real.py", proj / "src" / "link.py")
        os.symlink(str(outside), proj / "src" / "out.py")
    except OSError:
        pytest.skip("no symlinks here")
    assert ptm.owns_link_warnings(ptm.Plan.load(str(p)), proj) == [
        "WARNING: OWNS: T1 owns src/link.py, a symlink to lib/real.py; commit_task counts the target as owned, "
        "but name lib/real.py in Owns so review and lint see the file the task edits",
        f"WARNING: OWNS: T1 owns src/out.py, a symlink to {os.path.realpath(outside)} outside the repository; "
        "edits through it are never committed, so own a file inside the repository",
    ]
    assert ptm.owns_link_warnings(ptm.Plan.load(str(p)), None) == []


def test_also_touches_entries(tmp_path):
    _, p = proj_with(tmp_path, ALSO)
    assert ptm.also_touches_warnings(ptm.Plan.load(str(p))) == [
        "WARNING: ALSO-TOUCHES: T1 lists src/a.py, which it owns already; drop it from Also-touches",
        "WARNING: ALSO-TOUCHES: T1 lists src/z.py, which no task owns; put it in T1's Owns "
        "(Also-touches is for a file a later task owns)",
        "WARNING: ALSO-TOUCHES: T1 lists src/c.py, owned by T3, which does not depend on T1; Also-touches is for a file "
        "a later task owns (an edge T1 --> T3), so add that edge or move the edit to T3",
    ]


def test_lint_prints_the_new_warnings(tmp_path):
    proj, p = proj_with(tmp_path, ALSO)
    assert "WARNING: ALSO-TOUCHES: T1 lists src/z.py, which no task owns" in lint(tmp_path, proj, p)
    proj2, p2 = proj_with(tmp_path / "ui", UI)
    assert C2 in lint(tmp_path, proj2, p2)
