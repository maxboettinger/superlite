"""Every `sl` call written in the docs names a tool, subcommand, flag and flag choice the real parser still has."""
from __future__ import annotations

import copy
import itertools
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import doc_contract_parsers as dcp  # noqa: E402

REPO = HERE.parents[1]
ALLOWLIST = HERE / "doc_contract_allowlist.txt"
MAX_ALLOWED = 25

# --- extraction -------------------------------------------------------------------------------

_PATH_PART = r"""(?:<[^<>\s`]*>|[^\s`"'<>|;()])"""
LAUNCHER = (
    r"""(?:(?<![\w\-./$<>"'])sl"""  # bare sl, not inside a word, not sl-x
    r"""|"?\$\{?SL\}?"?"""  # "$SL" $SL ${SL}
    rf"""|"?{_PATH_PART}*/sl"?"""  # a path ending in /sl, quoted or not
    r"""|<[^<>`]*\bsl>)"""  # <abs sl>
)
CALL_RE = re.compile(LAUNCHER + r"""(?=\s)\s+(?P<tool>[a-z][a-z0-9_]*)(?![\w\-])""")
TOKEN_RE = re.compile(r"""\"[^\"]*\"|'[^']*'|\S+""")
SPAN_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
BARE_END = {"|", ";", "&&", ">", ")", "||", "&"}


def _tokens(rest: str, strict: bool) -> list[str]:
    out: list[str] = []
    for raw in TOKEN_RE.findall(rest):
        if raw in BARE_END or re.match(r"^\d*>", raw):
            break
        end = False
        tok = raw
        if not tok.startswith(("'", '"')):
            while tok and tok[-1] in ";)":
                end = True
                tok = tok[:-1]
            if not strict:
                while tok and tok[-1] in ".,:":
                    end = True
                    tok = tok[:-1]
            else:
                tok = tok.rstrip(".,:")
            tok = tok.lstrip("([")
            while tok.endswith("]") and "[" not in tok:
                tok = tok[:-1]
        if tok:
            out.append(tok)
        if end:
            break
    return out


def _calls_in(segment: str, strict: bool) -> list[tuple[bool, list[str]]]:
    found = []
    matches = list(CALL_RE.finditer(segment))
    for k, m in enumerate(matches):
        stop = matches[k + 1].start() if k + 1 < len(matches) else len(segment)
        rest = segment[m.start("tool"):stop]
        found.append((strict, _tokens(rest, strict)))
    return found


def extract_calls(text: str) -> list[tuple[int, bool, list[str]]]:
    calls = []
    fenced = False
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            calls += [(no, s, t) for s, t in _calls_in(line, True)]
            continue
        spans = [(m.start(), m.group(1)) for m in SPAN_RE.finditer(line)]
        for _, span in spans:
            calls += [(no, s, t) for s, t in _calls_in(span, True)]
        prose = SPAN_RE.sub(" ; ", line)
        calls += [(no, s, t) for s, t in _calls_in(prose, False)]
    return calls


# --- checking ---------------------------------------------------------------------------------

_PLACEHOLDERS = [
    r"<.*>", r"\$\{?\w+\}?", r"[A-Z][A-Z0-9_]*(?:[,.\-][A-Z0-9_]+)*", r"[TW]\d+", r"\d+(?:\.\d+)?",
    r"\.\.\.|…", r"\*", r"[\"'].*",
]
_PLACEHOLDER_RE = re.compile("^(?:" + "|".join(_PLACEHOLDERS) + ")$")


def _placeholder(tok: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(tok))


def _alternatives(tok: str) -> list[str]:
    if _placeholder(tok):
        return [tok]
    m = re.match(r"^(.*)\{([^{}]*,[^{}]*)\}(.*)$", tok)
    if m:
        return [m.group(1) + a + m.group(3) for a in m.group(2).split(",")]
    if "|" in tok:
        return [a for a in tok.split("|") if a]
    return [tok]


def _source(tool: str) -> str:
    for d in dcp.SCRIPT_DIRS:
        p = d / f"{tool}.py"
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
    return ""


def _check_one(tokens: list[str], trees: dict, strict: bool) -> list[str]:
    tool = tokens[0]
    tools = trees["tools"]
    if tool not in tools:
        return [f"unknown tool '{tool}'"] if strict else []
    node = tools[tool]
    problems: list[str] = []
    if node is None:
        src = _source(tool)
        for tok in tokens[1:]:
            if tok == "--":
                break
            if _placeholder(tok):
                continue
            word = tok.split("=")[0] if tok.startswith("--") else tok
            if (strict or tok.startswith("--")) and word not in src:
                problems.append(f"{tool}: '{word}' appears nowhere in {tool}.py")
        return problems
    chain = [node]
    path = [tool]
    label = lambda: " ".join(path)  # noqa: E731
    sub_phase = bool(node["subs"])
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok == "--":
            break
        if tok.startswith("--"):
            flag, eq, val = tok.partition("=")
            if not any(flag in n["flags"] for n in chain):
                problems.append(f"{label()}: no flag {flag}")
                sub_phase = False
                continue
            sub_phase = False
            choices = next((n["choices"][flag] for n in reversed(chain) if flag in n["choices"]), None)
            if choices is not None:
                if not eq:
                    if i >= len(tokens):
                        continue
                    val = tokens[i]
                    i += 1
                if val and not _placeholder(val) and val not in choices:
                    problems.append(f"{label()} {flag}: '{val}' is not one of {choices}")
            continue
        if tok.startswith("-") or _placeholder(tok):
            sub_phase = False
            continue
        if sub_phase and chain[-1]["subs"]:
            subs = chain[-1]["subs"]
            if tok in subs:
                chain.append(subs[tok])
                path.append(tok)
                sub_phase = bool(subs[tok]["subs"])
                continue
            if strict:
                problems.append(f"{label()}: '{tok}' is not a subcommand ({', '.join(sorted(subs))})")
            sub_phase = False
            if not strict:
                break
            continue
        sub_phase = False
    return problems


def check_call(tokens: list[str], trees: dict, strict: bool = True) -> list[str]:
    if not tokens:
        return []
    for i, tok in enumerate(tokens):
        alts = _alternatives(tok)
        if len(alts) > 1:
            seen: list[str] = []
            for alt in alts:
                for p in check_call(tokens[:i] + [alt] + tokens[i + 1:], trees, strict):
                    if p not in seen:
                        seen.append(p)
            return seen
    return _check_one(tokens, trees, strict)


# --- the doc scan -----------------------------------------------------------------------------

def _doc_files() -> list[Path]:
    files = sorted((REPO / "skills").rglob("*.md"))
    files += sorted((REPO / "commands").glob("*.md")) + sorted((REPO / "agents").glob("*.md"))
    files += sorted((REPO / "docs").glob("*.md")) + [REPO / "README.md"]
    return [f for f in files if f.is_file()]


def _scan(trees: dict) -> tuple[int, list[tuple[str, str, str]]]:
    count, found = 0, []
    for f in _doc_files():
        rel = f.relative_to(REPO).as_posix()
        for no, strict, tokens in extract_calls(f.read_text(encoding="utf-8")):
            if strict or tokens[0] in trees["tools"]:
                count += 1
            call = " ".join(tokens)
            for p in check_call(tokens, trees, strict):
                found.append((rel, call, f"{rel}:{no}: sl {call} -> {p}"))
    return count, found


def _allowlist() -> list[tuple[str, str, str]]:
    entries = []
    for raw in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#"):
            parts = [p.strip() for p in raw.split(" | ", 2)]
            entries.append((parts + ["", "", ""])[:3] if len(parts) < 3 else tuple(parts))
    return entries


def test_every_sl_call_in_the_docs_is_real():
    trees = dcp.parser_trees()
    count, found = _scan(trees)
    assert count > 150, f"only {count} calls found"
    allowed = {(p, c) for p, c, _ in _allowlist()}
    bad = sorted(line for p, c, line in found if (p, c) not in allowed)
    assert not bad, "doc calls the parsers do not know:\n" + "\n".join(bad)


def test_allowlist_is_reasoned_and_live():
    entries = _allowlist()
    assert len(entries) <= MAX_ALLOWED
    for e in entries:
        assert len(e) == 3 and all(x.strip() for x in e), f"entry needs 'path | call | reason': {e}"
    _, found = _scan(dcp.parser_trees())
    live = {(p, c) for p, c, _ in found}
    dead = [e for e in entries if (e[0], e[1]) not in live]
    assert not dead, f"allowlist entries that match no problem: {dead}"


# --- unit tests -------------------------------------------------------------------------------

def _trees():
    return dcp.parser_trees()


def test_renamed_flag_fails():
    call = ["fleet", "wait", "--wave", "--timeout", "540000", "--plan", ".superlite"]
    trees = copy.deepcopy(_trees())
    flags = trees["tools"]["fleet"]["subs"]["wait"]["flags"]
    flags[flags.index("--wave")] = "--wave-all"
    assert check_call(call, trees) == ["fleet wait: no flag --wave"]
    assert check_call(call, _trees()) == []


def test_made_up_calls_fail():
    t = _trees()
    assert check_call(["notatool"], t) == ["unknown tool 'notatool'"]
    bad = check_call(["backlog", "nosuchsub"], t)
    assert len(bad) == 1 and bad[0].startswith("backlog: 'nosuchsub' is not a subcommand (")
    assert check_call(["dispatch", "--no-such-flag"], t) == ["dispatch: no flag --no-such-flag"]
    assert check_call(["backlog", "ship", "B", "lock", "--wait", "500"], t) == []
    assert check_call(["orchestrator", "status"], t) == []
    assert check_call(["version"], t) == []


def test_extractor_reads_every_launcher_form():
    text = "\n".join([
        "run `sl fleet on --plan X` and `\"$SL\" pool busy ID Tn` then `$SL dispatch --cap 10`",
        "`<skill-dir>/../subagent-driven-development/scripts/sl orchestrator status` and `<abs sl> run_tests --full`",
        "```",
        '"/abs/scripts/sl" fleet off',
        "```",
    ])
    got = [(s, t) for _, s, t in extract_calls(text)]
    assert got == [
        (True, ["fleet", "on", "--plan", "X"]),
        (True, ["pool", "busy", "ID", "Tn"]),
        (True, ["dispatch", "--cap", "10"]),
        (True, ["orchestrator", "status"]),
        (True, ["run_tests", "--full"]),
        (True, ["fleet", "off"]),
    ]
    assert extract_calls("run `sl fleet wait --wave --plan .superlite` now") == [
        (1, True, ["fleet", "wait", "--wave", "--plan", ".superlite"])]


def test_extractor_skips_prose():
    text = "the host `sl:<repo>-w1` and `sl's` name, sl-w1 and the sl that runs it."
    calls = extract_calls(text)
    assert not [c for c in calls if c[1]]
    assert [p for _, s, t in calls for p in check_call(t, _trees(), s)] == []


def test_call_ends_at_pipes_and_spans():
    assert [t for _, _, t in extract_calls("`sl metrics | head`")] == [["metrics"]]
    assert [t for _, _, t in extract_calls("`sl orchestrator status; sl metrics`")] == [["orchestrator", "status"], ["metrics"]]
    assert [t for _, _, t in extract_calls("`sl metrics && sl dispatch`")] == [["metrics"], ["dispatch"]]
    assert check_call(["orchestrator", "set", "human|ai"], _trees()) == []


def _choice_flag():
    def walk(node, path):
        for flag, ch in node["choices"].items():
            yield path, flag, ch
        for name, sub in node["subs"].items():
            yield from walk(sub, path + [name])

    for tool, node in _trees()["tools"].items():
        if node:
            for hit in walk(node, [tool]):
                return hit
    raise AssertionError("no flag with choices")


def test_placeholders_and_alternatives():
    t = _trees()
    assert check_call(["backlog", "ship", "<B>", "lock", "--wait", "N"], t) == []
    assert check_call(["run_tests", "--fast", "PATHS", "--", "--anything"], t) == []
    path, flag, choices = _choice_flag()
    got = check_call(path + [flag, f"{choices[0]}|bogus"], t)
    assert len(got) == 1 and "'bogus'" in got[0] and "is not one of" in got[0]
