from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = {
    "probe": "- **`serve=` arguments.** A factory that needs arguments gets them in the entry: `serve=pkg.server.create_server(Workbook(), port=0)`. pt_review reads them with ast, never eval: literals; list, tuple, set and dict displays without a `**` entry; names and dotted names the serve module defines or imports; calls whose callee is a name or dotted name of the project's own code (a module file outside the standard library and site-packages); `*` and `**` arguments. Lint fails `PROBE: serve=<entry> arguments: <reason>; write literals, names of <module> and calls of the project's own code` for any other form (a lambda, subscript, operator, comprehension, f-string, or a name or attribute starting with `__`) and, once the serve module's file exists, for a name it does not bind (builtins such as `dict` included) and a callee it imports from the standard library (`Path(\"x\")` after `from pathlib import Path`). A third-party callee (`requests.Session()`) passes lint and fails only when contract part2 starts the server: build such an object inside the factory instead.",
    "stop": "on a fleet worker's stop (`Stop`, and `StopFailure` when a turn ends on an API error, whose record's `last` holds the API error text, #887),",
    "git": "- `block-unsafe-kill` also blocks a fleet worker's (`SUPERLITE_FLEET_WORKER` set, `SUPERLITE_FLEET_ROLE` not `lead`) `git checkout`, `git restore` and `git stash` in every form, also behind git's global options (`git -C <dir>`, `-c k=v`, `--git-dir`, `--work-tree`, `--no-pager`), which the `--disallowedTools` prefix rules of #784 miss; the coordinator and leads are not affected, and the gate line's rule is `worker-git` (#889).",
    "base": "`sl run_tests --base-skips [--plan DIR]` runs the newest full run's skipped tests (their test files) at the run's base commit (`checkpoints.json` `base`, else the merge-base with the default branch) in the scratch tree `.superlite/trees/base-skips`, removed afterwards, and writes `test-summary-base.json` (`mode` `base`, `base`, `full_started`, `compared`, `skipped_tests`, counts) and nothing else; it refuses every other mode flag (exit 2) (#886).",
    "tag": "The review packet appends ` (base skips too)` to each `- SKIPPED:` row whose test `test-summary-base.json` also lists as skipped (its `base` matching the packet's `--base`); with SKIPPED rows and no matching base file it prints `note: skipped tests not compared with the base; run <sl> run_tests --base-skips, then rebuild the packet` (#886).",
    "lint": "Plan lint `PROBE:` reads a `serve=target(args)` entry's arguments with the same ast walker as pt_review's runtime check and fails `PROBE: serve=<entry> arguments: <reason>; write literals, names of <module> and calls of the project's own code` for a form pt_review refuses; with the serve module's file on disk it also fails a name the module does not bind and a callee imported from the standard library (#891)."
}


def _has(path, key):
    assert S[key] in (ROOT / path).read_text(encoding="utf-8")


def test_probe_plan_serve_arguments():
    _has("skills/writing-plans/probe-plan.md", "probe")


def test_hooks_md_stopfailure():
    _has("docs/hooks.md", "stop")


def test_hooks_md_worker_git():
    _has("docs/hooks.md", "git")


def test_tools_md_base_skips():
    _has("docs/tools.md", "base")


def test_tools_md_packet_tag():
    _has("docs/tools.md", "tag")


def test_tools_md_serve_lint():
    _has("docs/tools.md", "lint")
