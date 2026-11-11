"""#493: docs/tools.md names the cross-run overlap warnings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
WT = ("Other open superlite runs of the repository (a worktree whose `.superlite/stable.json` names a plan, or a running, "
      "needs_decision or parked `backlog.json` batch with its worktree on disk) print on stderr: one `worktree: open run "
      "<label> at <path> owns N files: ...; keep your plan's Owns off them (plan lint warns on a shared file)` line each, "
      "or, once the run has a plan, `worktree: WARNING: OVERLAP: <files> also owned by open run <label> at <path>; the run "
      "that merges second merges the default branch first` for each run sharing a file with its Owns (#493, a warning only).")
PT = ("Lint prints `WARNING: OVERLAP: <file> (<tasks>), ... also owned by open run <label> at <path>; the run that merges "
      "second merges the default branch first` (a warning, never an issue) when a task's Owns share a file with another "
      "open superlite run of the repository (another worktree's plan, or an open `backlog.json` batch's files; #493).")
FIN = ("when the default branch (local, then `origin/`'s) moved since this branch left it in files the run owns (the "
       "plan's Owns, the branch's own changes and its uncommitted tracked changes) it prints `WARNING: <ref> moved in N "
       "files this run owns (K commits since this branch left it at <sha>): ...; merge <ref> into this branch before "
       "shipping (finishing skill: conflict step)` (#493);")


def row(name):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |"))


def test_rows_name_the_warnings():
    assert WT in row("worktree")
    assert PT in row("plan_tools")
    assert FIN in row("finish")
