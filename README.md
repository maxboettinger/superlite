<p align="center">
  <img src="assets/superlite-logo.svg" width="160" alt="superlite: a feather made of neurons">
</p>

<h1 align="center">superlite</h1>

<p align="center">
  <b>Hand an agent a spec. Come back to finished, tested work.</b><br>
  An autonomous, feather-light build workflow for Claude Code.
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-6366f1">
  <img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-2dd4bf">
  <img alt="parallel agents" src="https://img.shields.io/badge/parallel%20agents-up%20to%2018-c084fc">
</p>

---

## What it is

superlite plans a build, splits it into tasks that can run side by side, hands each task to the cheapest agent that can do it well, checks the seams, and reviews the result. You decide **who orchestrates**: you, or the AI.

- **Autonomous.** Describe the project, pick the AI orchestrator, and walk away. Decisions it has to make are recorded as rulings, not asked as questions.
- **Fast.** Up to 18 agents at once, a plan written for parallelism, and mechanical work on Haiku.

### Not a rival to superpowers

superlite is **not a competitor** to [superpowers](https://github.com/obra/superpowers). superpowers is a careful, collaborative workflow that keeps a human close to every step, and it is excellent at that. superlite starts from its ideas (the plugin layout, the session-start hook, the lifecycle skills, with credit) and tunes them for a different job: **autonomous development, at speed**. If you want to steer each step, use superpowers. If you want to hand over a spec and come back to working code, use superlite. Pick one per session.

---

## It is fast

Same machine, same task: build a Python site generator and a spreadsheet engine from one spec (`sitegen` + `minisheet`, 177 hidden tests), headless on Opus.

| What we measured | superpowers | superlite |
|---|---|---|
| Wall-clock to a finished build | 33.6 min (stock, 3 runs: 21.2 / 31.9 / 47.6)<br>23.5 min (orchestrated, 3 runs) | **16.1 min** |
| Faster than superpowers | | **52%** vs stock, **31%** vs orchestrated |
| Fastest-to-slowest spread, 3 runs | 26.4 min | **9.1 min** |
| Agents working at once | 3 to 4 | **up to 18** |
| Hidden tests passed | 177 / 177 | 177 / 177 (a tie, at higher speed) |
| Earlier 9-module benchmark (1 run each) | 34.4 min | **8.8 min** |
| superlite against its own first version | 26.9 min | **16.1 min** (40% faster) |

And it is not tied to one language. A TypeScript site generator went from spec to 132 / 132 hidden tests in **8.5 minutes**.

<sub>The 16.1 min figure is one run of the current build. The superpowers figures, the spread row (3 runs of each, on an earlier superlite build) and the 9-module row (the first version, 1 run each) come from earlier runs on the same machine, so treat the gaps as indications, not a statistical proof. superlite can cost more than superpowers and scores lower on the extra robustness probes (4 of 7 against about 5.7 of 7). Details, runs and caveats: [bench/](bench/) and the Benchmark section below.</sub>

---

## Pick how to use it

| Situation | Say something like | What happens |
|---|---|---|
| **MVP, a new project** | "Build me a static site generator from this spec" | One batch of questions, a plan, then parallel tasks on Sonnet and Haiku, package reviews and one fresh final review |
| **A feature on existing code** | "Add CSV export with column widths to the existing app" | The same flow, with seam checks between the new and the existing code. On a large codebase it offers to install Graphify (never without your yes) |
| **Debug** | "This test fails on leap days: find the root cause and fix it" | `systematic-debugging` finds the cause first; fixes go to fix-only agents by tier, each leaving a note, and escalate after two failed rounds |
| **A small change** | "Rename `build` to `render` everywhere" | Small work stays inline, with a reviewer always |
| **Review and harden** | "Review this branch and fix what you find" | Package reviewers fix their own findings; the final reviewer reports findings with tiers and never edits |
| **Many real sessions across accounts** | `sl fleet on`, then build as usual | Implementers run as Claude Code sessions in Herdr panes, one account per worker (docs/fleet.md) |
| **You approve first** | "Build X. I will approve the plan" | A human orchestrator: you get a plain-language review plan with diagrams; nothing runs until you say yes |
| **Hands off** | "Build X. I am away, decide yourself" | The AI orchestrator plans, lints, dispatches and rules on open choices without stopping |
| **Ship it** | "We are done: finish the branch" | Verification first, then merge or PR options. It never pushes without you |

**Start commands.** `/superlite:start` asks for the mode and who orchestrates; `/superlite:mvp <what>`, `/superlite:feature <change>` and `/superlite:debug <bug>` go straight to a mode. Say it in plain words instead if you prefer; the commands are shortcuts. Also: `/superlite:status`, `resume`, `stop`, `report`, `setup`, `human`, `ai`, `approve`, `review`, `small` and `finish`.

**Who orchestrates.** With a human orchestrator nothing is built, dispatched or written (except the review plan) until you reply approve; you review a plain-language plan with diagrams (a `.review.md`, about two pages, with a rough time and cost) **before** anything is linted or sent off; after your yes the coordinator rewrites it in the agent format (task graph, interfaces, examples, sizes) and runs it. With the AI orchestrator it does everything itself, with no review plan and no questions.

---

## Install

You need Claude Code, git, Python 3.10 or newer (the tools are Python; the project you build can be in any language), and `bash` (Git Bash on Windows). `uv` is optional.

```
/plugin marketplace add maxboettinger/superlite
/plugin install superlite@superlite-dev
```

Or load a local checkout for one session: `claude --plugin-dir <path-to-superlite>`

Open a fresh session and send `Let's make a react todo list`. A working install starts `brainstorming` before any code is written. The Pi install is in [Installation](#installation) below.

## Use it

1. **Describe what you want.** A paragraph or a spec file is enough.
2. **Choose the orchestrator** when asked: you validate the plan, or the AI does everything.
3. **Let it run.** Watch `.superlite/` in your project: `progress.md` has the rulings and the log, `test-summary.json` the latest test result, `metrics.jsonl` and the run history the time and cost per agent.

```mermaid
flowchart LR
  A([Your request]) --> B[Plan]
  B --> C[Build in parallel]
  C --> D[Review and fix]
  D --> E([Done])
```

---

## More

How it works, in [docs/](docs/): [how a run works](docs/how-a-run-works.md) · [skills and agents](docs/skills-and-agents.md) · [hooks](docs/hooks.md) · [testing](docs/testing.md) · [tools](docs/tools.md) · [config](docs/config.md) · [language support](docs/language.md) · [how the rules are enforced](docs/gates.md) · [an example review plan](docs/example-review-plan.md). Installation for Pi, the benchmark harness and the task list follow below.

---

## Configuration

- **`detail` (plan switch).** `writing-plans` records `**Detail:** contracts | tests | full` in the plan header, and a task can override it. `contracts` gives files, signatures and named tests with exact values. `tests` (the default) adds the test code verbatim and leaves the implementation to the implementer. `full` includes implementation code too, for tricky algorithms. `brainstorming` asks for it in its single batched question, and picks the default itself when unattended.
- **Final review.** The coordinator runs at medium effort. The final review is a fresh Opus `final-reviewer` at high effort: one turn, findings only, reading a review packet built from the logs, with a target under 30 s. It is not a fork, so `CLAUDE_CODE_FORK_SUBAGENT` is not needed.
- **Agent status summaries (hidden cost).** In the interactive CLI, Claude Code asks every background agent's model for a 3-5 word status line every 30 s, sending the agent's transcript, or a few hundred characters of notes when the server serves the short mode; superlite never reads it and the requests appear in no transcript, so the budget cannot count them (`agent_summary`, [anthropics/claude-code#86879](https://github.com/anthropics/claude-code/issues/86879)). There is no supported switch; `CLAUDE_CODE_FORK_SUBAGENT=0` in the `env` map of your settings closes the gate and costs only the `fork` subagent type, which superlite does not use. `/superlite:setup` checks it and offers to write it; a `budget:` line says `SUMMARIES ON` while it is missing. Headless runs (`claude -p`, the benchmark) never arm the timer.
- **Automatic compaction.** Set an auto-compact window once (`/superlite:setup` offers `"autoCompactWindow": 400000` for your user settings; `/autocompact 400k` does it for the current model) and a long orchestrator session compacts and continues by itself: Claude Code compacts at the window, superlite tells the summary what to keep (your goal and standing instructions, decisions, what is in flight, the next step) and afterwards tells the session to go on and shows it the run state. Without a window, a 1M-context model compacts only near its limit; past 500k tokens superlite says so once. `SUPERLITE_NO_AUTOCOMPACT=1` turns superlite's part off. Details: [hooks](docs/hooks.md), [config](docs/config.md).
- **Implementer cache TTL.** The implementer's frontmatter sets a 1-hour prompt cache TTL, so its history is still cached when fix rounds arrive waves later. Setting `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL=1h` in the environment does the same.
- **Context-budgeted sizing.** Each task in a plan carries an `Est. context` line, predicted from the lines it writes, the lines it reads and the docs it is handed, on top of the implementer's fixed ~18k prefix. Tasks predicted above 80k are split, tasks whose variable part is smaller than the prefix are merged with a neighbor, no task is predicted to run longer than about 3 minutes, there is no fixed wave size (the task graph sets the parallel width), and the whole plan stays under 15k chars because it doubles as the shared prime. The coefficients are fit on one project, so treat them as a guide.

## Installation

superlite runs on Claude Code and Pi. If you use both, install superlite separately for each one. Every integration loads `using-superlite` at session start; to verify, open a fresh session and send `Let's make a react todo list`. A working install triggers `brainstorming` before any code is written.

Each harness has a tool-mapping file in `skills/using-superlite/references/` (Pi, plus Claude Code notes). Where a harness has no plugin agents, each agent in `agents/` (`implementer`, `implementer-haiku`, `package-reviewer`, `final-reviewer` and the three fixers) runs as that harness's generic subagent with `agents/<name>.md` as its instructions.

### Claude Code

Load for one session from a local checkout:

    claude --plugin-dir <path-to-superlite>

Or add a local checkout as a marketplace:

    /plugin marketplace add <path-to-superlite>
    /plugin install superlite@superlite-dev

Or install from GitHub:

    /plugin marketplace add maxboettinger/superlite
    /plugin install superlite@superlite-dev

### Pi

Install superlite as a Pi package from this repository:

```bash
pi install git:github.com/maxboettinger/superlite
```

For local development, run Pi with a checkout loaded as a temporary package:

```bash
pi -e /path/to/superlite
```

The Pi package loads the superlite skills and a small extension that injects the `using-superlite` bootstrap into every request; the first message stays the same, so the prompt cache holds. Subagent and task-list tools remain optional Pi companion packages.

### Keeping versions in sync

The version lives in every manifest listed in `.version-bump.json`. Bump all of them with one command, and check for drift with `--check` or `--audit`:

```bash
scripts/bump-version.sh 0.2.0
scripts/bump-version.sh --check
```

## Benchmark

`bench/` holds a head-to-head harness: both plugins build the same 9-module project (`bench/task/SPEC.md`) headless on Opus, and a hidden 89-test suite scores the result. Run 1 (n=1 per arm; the runs overlapped):

| | superpowers 6.4.1 | superlite 0.1.0 |
|---|---|---|
| Wall-clock | 34.4 min | **8.8 min** (3.9× faster) |
| Hidden tests | 89 / 89 | 89 / 89 |
| Cost (API-equivalent) | $8.15 | **$3.28** (60% cheaper) |

Full write-up: [docs/benchmark-report.md](docs/benchmark-report.md). (An earlier version of these numbers overstated both costs because of a scoring bug; see the correction note in the report.)

### Running it

From the repo root. `harness.py` runs one arm headless and scores it against the hidden suite; `BENCH_TASK` picks a task from `bench/tasks/` (`combo`, `combo-planted`, `brownfield`, `ts-wordstat`, `ts-textkit`, `ts-logflow`, `ts-logflow-plus`, `ts-sitegen`).

    uv run --no-project python bench/harness.py run <arm> <rep> [--smoke]
    uv run --no-project python bench/harness.py score <arm> <rep>
    uv run --no-project python bench/harness.py rescore-tasks <arm> <rep>
    uv run --no-project python bench/harness.py report

Arms are `superpowers` and `superlite`. Environment variables: `SUPERLITE_PLUGIN_DIR` points the superlite arm at another plugin directory (for example a worktree of an older commit, as a frozen baseline); `BENCH_PROMPT_SUFFIX` appends text to the task prompt.

Analysis scripts:

    python bench/report_mechanical.py bench/results/combo-superlite-x1.mechanical.json bench/results/*.json
    python bench/report_mechanical.py --history ~/.superlite/history.jsonl [--focus opus,haiku] [--baseline sonnet]
    python bench/mechanical_ab.py RUN_DIR [--tasks T8,T5] [--n 3] [--cost-cap 2.0] [--timeout 300] [--dry-run] [--wait]
    python bench/routing_evidence.py [--write]
    python bench/build_shape_audit.py [--runs DIR] [--write]
    python bench/predict_calibration.py [--write]

`report_mechanical` compares tasks by agent and model. `mechanical_ab` replays `Kind: mechanical` tasks on Haiku and on the Sonnet implementer. `routing_evidence` gives per-band outcomes by model and a routing recommendation. `build_shape_audit` shows what each task graph costs and which edges could go. `predict_calibration` shows why predicted times miss and fits a model on real runs.

## Tasks

- [ ] **Superlite 0.3: a task-graph flow that aims at half of superpowers' time.** The design is in `C:\Work\Planning\Specs\2026-10-17-superlite-architecture-design.md` (D10-D18, G1, R1). Steps:
  - Smoke-test the 0.3 tools and agents.
  - Combined task (`bench/tasks/combo`), 3 reps, arms in parallel.
  - E12: planted defects (`bench/tasks/combo-planted`), 3 reps with and without the incident log.
  - E13: brownfield (`bench/tasks/brownfield`), 3 reps with and without Graphify.

  Done when the superlite median is at most 0.5x superpowers' on the combined task (G1) at equal hidden-test score and robustness of at least 6/7, and the E12 and E13 effects are measured.

## Note

Do not enable superlite at the same time as superpowers. They share skill names and both inject session context, so they conflict.

## License

MIT
