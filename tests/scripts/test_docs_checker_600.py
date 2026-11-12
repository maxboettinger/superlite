"""#600: the docs name the checker role, the Running-app checks section and the simulator limits it meets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
FLEET_CHECKER = ("- Checker: `--role checker` (`superlite:checker`; fleet off: Agent `superlite:checker`), one turn, for a plan's "
                 "`## Running-app checks` once every task is committed, before the review packet. Brief "
                 "`.superlite/briefs/check-<round>.md`: the absolute `sl` path, `PLAN`, `ROOT`, the target (scheme or app, platform, "
                 "device type; a web app: its start command), the build command and the `C<n>` lines. Its standing rules (own "
                 "`sl-check-<worktree>` simulator, `.build/CheckDerivedData`, throwaway renders through `render_edit`) are in "
                 "`agents/checker.md`. It answers one `C<n> PASS|FAIL|NOT REACHABLE` line per check and writes its screenshots and "
                 "`index.md` lines into `.superlite/render/`; FAIL findings go to fixers (`fixing.md`); at freeze delete the "
                 "simulators its `Simulators:` line names.")
SDD_CHECKER = "A plan's `## Running-app checks` run here once, by a checker (fleet.md); FAIL lines are findings."
WP_RULE = ("- **Running-app checks.** A check that needs the running artifact (a simulator, the built macOS app, a widget, an app "
           "extension, a browser page) is never a plan task or a task step: an implementer skips it or cannot reach it. List each "
           "in a `## Running-app checks` section, one `- C<n>: <target>; reach: <state>; see: <what must show>` line per check. "
           "The coordinator runs them once, after every task is committed and before the final review packet, with a checker "
           "(`superlite:checker`, `../subagent-driven-development/fleet.md`), whose agent file holds the standing rules (own "
           "simulator, own build folder, screenshots in `.superlite/render/`).")
WP_FLAG = ("| \"Last task: integration and simulator check\" | Not a task: `## Running-app checks` lines a checker runs before "
           "the final review. |")
LIMITS_TAIL = (
    "## SwiftUI previews: no command-line renderer\n\n"
    "Seen: superlite 1.5.123, in fleet package reviews ([#600](https://github.com/maxboettinger/superlite/issues/600)).\n\n"
    "Xcode renders `#Preview` blocks only inside Xcode: the Xcode MCP `RenderPreview` tool needs a running Xcode, and fleet "
    "workers start without MCP servers. Two reviewers rendered PNGs with throwaway hosted tests instead and left them in the tree.\n\n"
    "What to do: a checker renders a view no running state reaches with a throwaway `ImageRenderer` snapshot test, recorded "
    "with `sl render_edit start <file>` and undone with `sl render_edit restore` (`agents/checker.md`).\n\n"
    "## macOS: no simulator for a render check\n\n"
    "Seen: superlite 1.5.109 ([#600](https://github.com/maxboettinger/superlite/issues/600)). With no macOS render check, "
    "every macOS UI batch ended with a live check left for the user; 36 piled up after about 60 batches.\n\n"
    "What to do: a checker launches the built `.app` and captures it with `screencapture -x` (`agents/checker.md`). Untried: "
    "whether a fleet pane's terminal has the Screen Recording permission `screencapture` needs; a refused or blank capture is "
    "NOT REACHABLE.\n")
AGENTS_LINE = ("- `checker` (sonnet, high): a one-turn worker that runs the built app, widget or extension once on its own "
               "simulator (or on macOS, or in a browser) and reports each listed check PASS, FAIL or NOT REACHABLE with "
               "screenshots; never fixes.")


def lines(p):
    return p.read_text(encoding="utf-8").split("\n")


def test_fleet_md_names_the_checker_after_research():
    ls = lines(SDD / "fleet.md")
    assert ls.count(FLEET_CHECKER) == 1
    assert ls[ls.index(FLEET_CHECKER) - 1].startswith("- Research: `--role research`")


def test_sdd_runs_the_checks_before_the_packet():
    t = (SDD / "SKILL.md").read_text(encoding="utf-8")
    assert t.count(SDD_CHECKER + " Then build the packet:") == 1
    assert t.index(SDD_CHECKER) < t.index("plan_tools packet --plan")
    assert len(t) <= 13300


def test_writing_plans_names_running_app_checks():
    t = (ROOT / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
    ls = t.split("\n")
    assert "9. **Running-app checks:** a UI, widget, app extension or browser target (Review Focus rules)." in ls
    assert "10. **Self-review.**" in ls and "9. **Self-review.**" not in ls
    assert ls.count(WP_RULE) == 1 and "RenderPreview" in ls[ls.index(WP_RULE) - 1]
    assert "since in-process agents inherit the session's MCP tools (fleet workers start without them);" in t
    assert ls.count(WP_FLAG) == 1 and ls[ls.index(WP_FLAG) - 1].startswith("| ")


def test_simulator_limits_gain_two_entries():
    t = (ROOT / "docs" / "simulator-limits.md").read_text(encoding="utf-8")
    assert t.endswith("\n\n" + LIMITS_TAIL)


def test_agents_doc_lists_the_checker_after_fixer_opus():
    ls = lines(ROOT / "docs" / "skills-and-agents.md")
    assert ls.count(AGENTS_LINE) == 1 and ls[ls.index(AGENTS_LINE) - 1].startswith("- `fixer-opus` (opus, high)")
