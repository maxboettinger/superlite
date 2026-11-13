#!/usr/bin/env python3
"""Fleet roles: which agent, model and effort a worker of each superlite role starts with.

Library: launch(role, tier, cfg, agents_dir) -> the claude argv and flags for one worker; env(role) -> the env a
worker of that role gets. Roles: implementer (the default), fixer, package-reviewer, final-reviewer, research, checker, writer.
Effort comes from the agent file's frontmatter, since frontmatter `effort` is ignored in a main-thread session
(`--effort` is passed instead). Stdlib only.
"""
# Complexity notation:
# f = lines of an agent file's frontmatter
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

import routing  # noqa: E402 | O(1)

AGENTS = Path(__file__).resolve().parents[3] / "agents"  # O(1)
ROLES = ("implementer", "fixer", "package-reviewer", "final-reviewer", "research", "checker", "writer")  # O(1)
FIXER_AGENTS = {"1": "superlite:fixer-sonnet", "sonnet": "superlite:fixer-sonnet",  # O(1) tiers of fixing.md
                "2": "superlite:fixer-sonnet-high", "sonnet-high": "superlite:fixer-sonnet-high",
                "3": "superlite:fixer-opus", "opus": "superlite:fixer-opus"}
REVIEWERS = {"package-reviewer": "superlite:package-reviewer", "final-reviewer": "superlite:final-reviewer"}  # O(1)
BRIEF_ONLY = ("No prime and no plan run: this brief is your whole task (no READY reply, no `sl task`, no `commit_task`). "  # O(1)
              "Commit only the files you changed and their tests with plain `git add <files>` and `git commit` in the brief's folder; "
              "for this task that replaces your agent file's prime, task-message and commit rules.")
NO_TIER = "%s takes no --tier (its agent file sets the model); --tier works for implementer, fixer, research and writer"  # O(1)
TAIL = ["--disallowedTools", "AskUserQuestion"]  # O(1) a worker never asks the user
RESEARCH_TAIL = TAIL + ["Edit", "Write", "NotebookEdit", "Bash"]  # O(1) research is read-only by its tools, not by prose


def frontmatter(agent: str, agents_dir: Path) -> dict:  # O(f)
    """The `key: value` lines between the first two `---` lines of the agent's file; a missing file is {}."""
    try:  # O(1)
        lines = (Path(agents_dir) / (agent.split(":", 1)[-1] + ".md")).read_text(encoding="utf-8").splitlines()  # O(file)
    except OSError:  # O(1)
        return {}  # O(1)
    if not lines or lines[0].strip() != "---":  # O(1)
        return {}  # O(1)
    out = {}  # O(1)
    for line in lines[1:]:  # O(f)
        if line.strip() == "---":  # O(1)
            break  # O(1)
        key, sep, value = line.partition(":")  # O(1)
        if sep and not line[:1].isspace():  # nested keys (experimental: cacheTtl) are skipped | O(1)
            out[key.strip()] = value.strip()  # O(1)
    return out  # O(f)


def launch(role: str, tier: str | None, cfg: dict, agents_dir: Path = AGENTS, output: str | None = None, brief: bool = False) -> dict:  # O(f)
    """The agent, flags and argv of one worker; `output` (an absolute path) is read by the writer role only.
    `brief` makes an implementer a one-turn, pool-less worker with no prime; other roles ignore it."""
    if role not in ROLES:  # O(1)
        raise ValueError("unknown role %s; use %s" % (role, ", ".join(ROLES)))  # O(1)
    pin = None  # the model the flags pin; None leaves it to the agent file | O(1)
    if role == "implementer":  # O(1)
        pin = tier or "sonnet"  # O(1)
        agent = routing.tier_agent(cfg, pin)  # O(1)
    elif role == "fixer":  # O(1)
        if tier is not None and tier not in FIXER_AGENTS:  # O(1)
            raise ValueError("fixer tier must be 1, 2, 3, sonnet, sonnet-high or opus")  # O(1)
        agent = FIXER_AGENTS[tier or "sonnet"]  # O(1)
    elif role == "research":  # O(1)
        agent = "superlite:researcher"  # O(1)
        pin = tier or "sonnet"  # O(1) researchers default to sonnet
    elif role == "writer":  # O(1)
        if not output:  # O(1)
            raise ValueError("writer needs an output file (the brief's Output: line)")  # O(1)
        if tier is not None and tier not in ("sonnet", "opus", "haiku"):  # O(1)
            raise ValueError("writer tier must be sonnet, opus or haiku")  # O(1)
        agent = "superlite:writer"  # O(1)
        pin = tier or "sonnet"  # O(1)
    elif role == "checker":  # O(1)
        if tier is not None:  # O(1)
            raise ValueError(NO_TIER % "checker")  # O(1)
        agent = "superlite:checker"  # O(1)
    else:  # O(1)
        if tier is not None:  # O(1)
            raise ValueError(NO_TIER % role)  # O(1)
        agent = REVIEWERS[role]  # O(1)
    fm = frontmatter(agent, agents_dir)  # O(f)
    effort = fm.get("effort") or None  # O(1)
    argv = ["--agent", agent] + (["--model", pin] if pin else []) + (["--effort", effort] if effort else []) + (RESEARCH_TAIL if role == "research" else TAIL)  # O(1)
    if role == "writer":  # only the one output file is writable; every other write is a dialog the fleet hook refuses | O(1)
        argv = argv[:-len(TAIL)] + ["--permission-mode", "default", "--allowedTools", "Edit(/" + Path(output).as_posix() + ")",  # O(1)
                                    "--disallowedTools", "AskUserQuestion", "Bash", "NotebookEdit"]
    solo = brief and role == "implementer"  # O(1)
    one_turn = role != "implementer" or solo  # O(1)
    return {"role": role, "agent": agent, "model": pin or fm.get("model") or None, "effort": effort, "argv": argv,  # O(1)
            "prime": role == "implementer" and not solo, "pool": role == "implementer" and not solo, "one_turn": one_turn}


def env(role: str) -> dict:  # O(1)
    return {"SUPERLITE_FLEET_ROLE": role, "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0"}  # O(1)
