#!/usr/bin/env python3
"""Fleet roles: which agent, model and effort a worker of each superlite role starts with.

Library: launch(role, tier, cfg, agents_dir) -> the claude argv and flags for one worker; env(role) -> the env a
worker of that role gets; research_bash_refusal(command) and research_hook(payload) hold the in-process researcher's Bash to
the read-only allowlist (CLI: `fleet_roles.py research-bash`, hook payload on stdin). Roles: implementer (the default), fixer, package-reviewer, final-reviewer, research, checker, writer.
Effort comes from the agent file's frontmatter, since frontmatter `effort` is ignored in a main-thread session
(`--effort` is passed instead). Stdlib only.
"""
# Complexity notation:
# f = lines of an agent file's frontmatter
import fnmatch  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

import routing  # noqa: E402 | O(1)

AGENTS = Path(__file__).resolve().parents[3] / "agents"  # O(1)
SKILLS = Path(__file__).resolve().parents[2]  # O(1) the plugin's skills folder (scripts -> subagent-driven-development -> skills)
ROLES = ("implementer", "fixer", "package-reviewer", "final-reviewer", "research", "checker", "writer")  # O(1)
FIXER_AGENTS = {"1": "superlite:fixer-sonnet", "sonnet": "superlite:fixer-sonnet",  # O(1) tiers of fixing.md
                "2": "superlite:fixer-sonnet-high", "sonnet-high": "superlite:fixer-sonnet-high",
                "3": "superlite:fixer-opus", "opus": "superlite:fixer-opus"}
REVIEWERS = {"package-reviewer": "superlite:package-reviewer", "final-reviewer": "superlite:final-reviewer"}  # O(1)
BRIEF_ONLY = ("No prime and no plan run: this brief is your whole task (no READY reply, no `sl task`, no `commit_task`). "  # O(1)
              "Commit only the files you changed and their tests with plain `git add <files>` and `git commit` in the brief's folder; "
              "for this task that replaces your agent file's prime, task-message and commit rules.")
NO_TIER = "%s takes no --tier (its agent file sets the model); --tier works for implementer, fixer, research and writer"  # O(1)
GIT_DENY = ("Bash(git checkout *)", "Bash(git restore *)", "Bash(git stash)", "Bash(git stash *)")  # O(1) a worker never rewrites the shared tree (#784)
TAIL = ["--disallowedTools", "AskUserQuestion", *GIT_DENY]  # O(1) a worker never asks the user
RESEARCH_BASH = ("Bash(git log *)", "Bash(git show *)", "Bash(git diff *)", "Bash(git status *)", "Bash(git blame *)",  # O(1) read-only commands the researcher may run (#809)
                 "Bash(git ls-files *)", "Bash(git rev-parse *)", "Bash(git merge-base *)", "Bash(git cat-file *)",  # O(1)
                 "Bash(git worktree list *)", "Bash(git apply --check *)", "Bash(ls *)", "Bash(xcrun simctl list *)")  # O(1)
RESEARCH_DENY = ("Bash(git * --output*)", "Bash(git apply * --apply*)", "Bash(git apply * --build-fake-ancestor*)",
                "Bash(git apply * --no-check*)")  # O(1) the allowlisted forms that write a file or apply a patch (#809)
RESEARCH_TAIL = ["--permission-mode", "dontAsk", "--allowedTools", "Read", "Grep", "Glob", *RESEARCH_BASH,  # O(1) dontAsk refuses every off-list command without a dialog (#809)
                 "--disallowedTools", "AskUserQuestion", *GIT_DENY, *RESEARCH_DENY, "Edit", "Write", "NotebookEdit"]  # O(1)
RESEARCH_AGENT = "superlite:researcher"  # the agent_type the Bash hook holds to the allowlist (#987) | O(1)
RESEARCH_DENY_WHY = {"Bash(git * --output*)": "writes a file (--output)", "Bash(git apply * --apply*)": "applies a patch (--apply)",
                     "Bash(git apply * --build-fake-ancestor*)": "writes a file (--build-fake-ancestor)",
                     "Bash(git apply * --no-check*)": "applies a patch (--no-check)"}  # O(1)
GIT_APPLY_READ_ONLY = frozenset(("--check", "--stat", "--numstat", "--summary", "-v", "--verbose", "-q", "--quiet", "-R", "--reverse", "-z", "-p", "-C",  # O(1)
                                 "--unidiff-zero", "--recount", "--allow-empty", "--ignore-space-change", "--ignore-whitespace", "--cached", "--index",  # O(1)
                                 "--binary", "--allow-binary-replacement", "--inaccurate-eof"))  # O(1) the git apply options a researcher may pass (#987)


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


def skills_read(argv: list[str], skills: str | Path | None = None, project: str | Path | None = None) -> list[str]:  # O(n) a copy of argv with the read-only plugin skills rule in its one --allowedTools list (#905)
    folder = (SKILLS if skills is None else Path(skills) if not isinstance(skills, str) else skills)  # O(1)
    base = folder.as_posix() if isinstance(folder, Path) else folder  # O(1)
    rule = "Read(/" + base.rstrip("/") + "/**)"  # O(1)
    out = list(argv)  # O(n)
    if rule in out:  # O(n)
        return out  # O(1)
    if project is not None:  # the project is readable already  # O(len)
        try:  # O(1)
            Path(folder).resolve().relative_to(Path(project).resolve())  # O(len)
            return out  # O(1)
        except ValueError:  # O(1)
            pass  # O(1)
    if "--allowedTools" in out:  # the list ends at the next argument that starts with -- | O(n)
        i = out.index("--allowedTools") + 1  # O(n)
        while i < len(out) and not out[i].startswith("--"):  # O(n)
            i += 1  # O(1)
        out.insert(i, rule)  # O(n)
    elif "--disallowedTools" in out:  # O(n)
        i = out.index("--disallowedTools")  # O(n)
        out[i:i] = ["--allowedTools", rule]  # O(n)
    else:  # O(1)
        out += ["--allowedTools", rule]  # O(1)
    return out  # O(1)


def env(role: str) -> dict:  # O(1)
    return {"SUPERLITE_FLEET_ROLE": role, "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0"}  # O(1)


def _rule_words(rule: str) -> list[str]:  # O(r)
    """The words of a `Bash(<p>)` rule's pattern."""
    return rule[len("Bash("):-1].split()  # O(r)


def _matches(tokens: list[str], words: list[str]) -> bool:  # O(t * w)
    """Word-wise match: `*` takes zero or more words, any other token one word by fnmatch, a last token ending in `*` the rest."""
    if not tokens:  # O(1)
        return not words  # O(1)
    tok = tokens[0]  # O(1)
    if tok == "*":  # O(w)
        return any(_matches(tokens[1:], words[i:]) for i in range(len(words) + 1))  # O(t * w)
    if not words or not fnmatch.fnmatchcase(words[0], tok):  # O(1)
        return False  # O(1)
    if len(tokens) == 1 and tok.endswith("*"):  # O(1)
        return True  # O(1)
    return _matches(tokens[1:], words[1:])  # O(t)


def _seg_text(seg) -> str:  # O(w)
    """The refused segment as text: the subshell, the words, then each redirect as `<op> <target>`."""
    parts = (["(%s)" % seg.subshell] if seg.subshell is not None else []) + list(seg.words)  # O(w)
    return " ".join(parts + ["%s %s" % (r.op, r.target) for r in seg.redirects])  # O(w)


def _redirect_ok(r) -> bool:  # O(1)
    """Whether a redirect only discards output, duplicates an fd or reads a file."""
    if r.op in (">", ">>", ">|", "&>", "&>>"):  # O(1)
        return r.target == "/dev/null"  # O(1)
    if r.op in (">&", "<&"):  # O(1)
        return r.target == "-" or r.target.isdigit()  # O(1)
    return r.op == "<" and "$" not in r.target and "`" not in r.target  # O(1)


def _spell_deny_flags(words: list[str]) -> list[str]:  # O(w * rules)
    """The words with each abbreviated deny flag spelled out: git takes unambiguous long-option prefixes (`--ap` is `--apply`)."""
    flags = [t[:-1] for rule in RESEARCH_DENY for t in _rule_words(rule) if t.startswith("--") and t.endswith("*")]  # O(rules)
    out = []  # O(1)
    for w in words:  # O(w)
        name, eq, rest = w.partition("=")  # O(1)
        full = next((f for f in flags if len(name) >= 4 and f.startswith(name)), None)  # O(rules)
        out.append(full + eq + rest if full else w)  # O(1)
    return out  # O(1)


def _git_glob_before_dashdash(seg) -> bool:  # O(w)
    """Whether a git segment has an unquoted glob word before its first `--` word (a file named `--output=x` would join the arguments)."""
    if not seg.words or seg.words[0] != "git":  # O(1)
        return False  # O(1)
    for i, w in enumerate(seg.words):  # O(w)
        if w == "--":  # O(1)
            return False  # O(1)
        if i < len(seg.globs) and seg.globs[i] == "g":  # O(1)
            return True  # O(1)
    return False  # O(1)


def _git_apply_option_off_list(words: list[str]) -> bool:  # O(w)
    """Whether a `git apply` word before the first `--` is an option off GIT_APPLY_READ_ONLY (exact words, no abbreviations or clusters)."""
    for w in words[2:]:  # O(w)
        if w == "--":  # O(1)
            return False  # O(1)
        if not w.startswith("-"):  # O(1)
            continue  # O(1)
        if w in GIT_APPLY_READ_ONLY or (w[:2] in ("-p", "-C") and w[2:].isdigit() and w[2:].isascii()):  # O(1)
            continue  # O(1)
        name, eq, value = w.partition("=")  # O(1)
        if eq and value and name in ("--whitespace", "--include", "--exclude", "--directory"):  # O(1)
            continue  # O(1)
        return True  # O(1)
    return False  # O(1)


def research_bash_refusal(command: str) -> str | None:  # O(n * rules)
    """None when every simple command of `command` is on RESEARCH_BASH, else why the first refused one is not."""
    import guard_lex  # O(1)
    try:  # O(1)
        segs = guard_lex.split(command)  # O(n)
    except Exception as e:  # O(1)
        return "could not read the command (%s)" % type(e).__name__  # O(1)
    for seg in segs:  # O(n)
        why = None  # O(1)
        if seg.subshell is not None:  # O(1)
            why = "runs a subshell"  # O(1)
        elif seg.bodies:  # O(1)
            why = "runs a substitution"  # O(1)
        elif any(seg.dyn) or _git_glob_before_dashdash(seg):  # O(w)
            why = "expands a value"  # O(w)
        elif any(r.op in ("<<", "<<-", "<<<") for r in seg.redirects):  # O(1)
            why = "reads a heredoc or here-string"  # O(1)
        elif not all(_redirect_ok(r) for r in seg.redirects):  # O(1)
            why = "redirects into a file"  # O(1)
        elif not seg.words:  # O(1)
            continue  # O(1)
        else:  # O(rules * w)
            deny_words = _spell_deny_flags(seg.words)  # O(w * rules)
            for rule in RESEARCH_DENY:  # O(rules)
                if _matches(_rule_words(rule), deny_words):  # O(w)
                    why = RESEARCH_DENY_WHY[rule]  # O(1)
                    break  # O(1)
            else:  # O(rules * w)
                if seg.words[:2] == ["git", "apply"] and _git_apply_option_off_list(seg.words):  # O(w)
                    why = "git apply option off the read-only list"  # O(1)
                elif not any(_matches(_rule_words(rule), seg.words) for rule in RESEARCH_BASH):  # O(rules * w)
                    why = "not on the allowlist"  # O(1)
        if why:  # O(1)
            return "%s: %s" % (why, _seg_text(seg))  # O(w)
    return None  # O(1)


def research_hook(text: str) -> tuple[int, str]:  # O(n)
    """(2, message) when the payload is the researcher's Bash call and it is refused, else (0, "")."""
    import json  # O(1)
    try:  # O(1)
        data = json.loads(text)  # O(n)
    except ValueError:  # O(1)
        return 0, ""  # O(1)
    if not isinstance(data, dict) or data.get("agent_type") != RESEARCH_AGENT or data.get("tool_name") != "Bash":  # O(1)
        return 0, ""  # O(1)
    tool_input = data.get("tool_input")  # O(1)
    command = tool_input.get("command") if isinstance(tool_input, dict) else None  # O(1)
    if not isinstance(command, str):  # O(1)
        return 0, ""  # O(1)
    why = research_bash_refusal(command)  # O(n)
    if why is None:  # O(1)
        return 0, ""  # O(1)
    names = ", ".join(r[len("Bash("):-len(" *)")] for r in RESEARCH_BASH)  # O(rules)
    return 2, "\n".join([  # O(1)
        "Blocked: the researcher runs only read-only commands (hooks/researcher-bash, #987): %s." % why,
        "Allowed, alone or joined by &&, ||, ;, & or |: %s; never --output; git apply --check only with read-only options (no --apply, "
        "--no-check, --build-fake-ancestor, --3way or --reject); no $(...), backticks, <(...), variables, subshells, heredocs or redirects "
        "into a file (2>/dev/null, 2>&1 and < file are fine)." % names,
        "A refused command is an answer: say what you could not check and never retry it another way."])


def main(argv: list[str]) -> int:  # O(n)
    if argv != ["research-bash"]:  # O(1)
        print("usage: fleet_roles.py research-bash (hook payload on stdin)", file=sys.stderr)  # O(1)
        return 2  # O(1)
    code, msg = research_hook(sys.stdin.read())  # O(n)
    if msg:  # O(1)
        print(msg, file=sys.stderr)  # O(1)
    return code  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main(sys.argv[1:]))  # O(1)
