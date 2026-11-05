"""Tools and interpreters: name the paths a simple command writes.

targets(words) takes the already-decoded words of one simple command (the lexer did the quoting) and returns the
paths it writes, as written: "." for a whole-tree discard (git reset --hard), "?" for a write whose target is not
literal, a directory with a trailing "/" for an extraction into it. COMMANDS holds the lower-case command names this
module reads (a path and ".exe" are stripped from the command word first).
"""

import os
import re
import shlex

import guard_files
import guard_lex

_PY = re.compile(r"^(python|pypy|py)[\d.]*$")  # O(1)
_NODE = frozenset({"node", "nodejs", "bun"})
_SEVENZ = frozenset({"7z", "7za", "7zr", "7zz"})
_TARS = frozenset({"tar", "bsdtar", "gtar", "gnutar"})
_PS_ALIAS = {"ri": "remove-item", "del": "remove-item", "erase": "remove-item", "rd": "remove-item",
             "copy": "copy-item", "cpi": "copy-item", "move": "move-item", "mi": "move-item", "ren": "rename-item",
             "rni": "rename-item", "sc": "set-content", "ac": "add-content", "ni": "new-item", "clc": "clear-content",
             "tee-object": "tee-object", "export-csv": "export-csv", "export-clixml": "export-clixml",
             "expand-archive": "expand-archive", "invoke-webrequest": "invoke-webrequest", "iwr": "invoke-webrequest",
             "invoke-restmethod": "invoke-webrequest", "irm": "invoke-webrequest"}
_PS_CMDLETS = frozenset({
    "set-content", "add-content", "clear-content", "out-file", "new-item", "remove-item", "copy-item", "move-item",
    "rename-item",
}) | frozenset(_PS_ALIAS)
COMMANDS: frozenset[str] = frozenset(
    {"git", "cpio", "ruby", "php", "perl", "unzip", "python", "python3", "python2", "py", "pypy", "pypy3"}
    | _TARS | _NODE | _SEVENZ | _PS_CMDLETS
)


def _cmd(word: str) -> str:  # O(len(word))
    base = re.split(r"[/\\]", word)[-1].lower()  # O(len(word))
    return base[:-4] if base.endswith(".exe") else base  # O(1)


def _join(base: str, p: str) -> str:  # O(len(base) + len(p))
    """p below the directory base; base "" or "." leaves p alone."""
    if not base or base == "." or p == "?" or p.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", p):  # O(1)
        return p  # O(1)
    if p in (".", "./", ""):  # O(1)
        return base  # O(1)
    while p.startswith("./"):  # O(len(p))
        p = p[2:]  # O(len(p))
    return base.rstrip("/") + "/" + p  # O(len(base) + len(p))


def _dirp(d: str) -> str:  # O(len(d))
    return d if d.endswith(("/", "\\")) else d + "/"  # O(len(d))


def _uniq(items: list[str]) -> list[str]:  # O(n)
    out: list[str] = []  # O(1)
    for i in items:  # O(n)
        if i not in out:  # O(n)
            out.append(i)  # O(1)
    return out  # O(1)


# ---------------------------------------------------------------- git

_GIT_VALOPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--exec-path",
                          "--config-env"})
_GIT_CMDS = frozenset(
    "add am annotate apply archive bisect blame branch bundle cat-file check-ignore checkout checkout-index cherry "
    "cherry-pick clean clone commit config count-objects describe diff diff-files diff-index diff-tree difftool fetch "
    "format-patch fsck gc grep help init log ls-files ls-remote ls-tree merge merge-base mergetool mv notes prune pull "
    "push range-diff read-tree rebase reflog remote repack replace reset restore rev-list rev-parse revert rm "
    "shortlog show show-ref sparse-checkout stash status submodule switch symbolic-ref tag update-index update-ref "
    "version worktree write-tree".split()
)
_GIT_SKIP = frozenset({"-s", "--source", "-b", "-B", "--orphan", "-e", "--exclude"})  # an option and its word
_GIT_VALLETTERS = {"clean": "e", "restore": "s", "checkout": "bB", "switch": "cC"}


def _git_flag(args: list[str], short: str, long: str, sub: str) -> bool:  # O(len(args))
    """args hold --LONG (also shortened to a prefix) or -SHORT in a cluster, read up to the first value letter."""
    vals = _GIT_VALLETTERS.get(sub, "")  # O(1)
    for a in args:  # O(len(args))
        if a == "--":  # O(1)
            return False  # O(1)
        if a.startswith("--"):  # O(1)
            o = a[2:].split("=", 1)[0]  # O(len(a))
            if long and o and long.startswith(o):  # O(len(o))
                return True  # O(1)
        elif a.startswith("-") and short:  # O(1)
            for ch in a[1:]:  # O(len(a))
                if ch == short:  # O(1)
                    return True  # O(1)
                if ch in vals:  # O(1)
                    break  # O(1)
    return False  # O(1)


_GIT_OUT = frozenset({"diff", "log", "show", "format-patch", "archive", "diff-tree", "diff-index", "diff-files",
                      "range-diff", "whatchanged", "show-branch"})


def _git_out(sub: str, args: list[str], base: str) -> list[str]:  # O(len(args))
    """--output=FILE (also shortened), format-patch -o DIR, archive -o FILE: the file or folder written."""
    out: list[str] = []  # O(1)
    names = ("output", "output-directory") if sub == "format-patch" else ("output",)  # O(1)
    i = 0  # O(1)
    while i < len(args):  # O(len(args))
        a = args[i]  # O(1)
        i += 1  # O(1)
        if a == "--":  # O(1)
            break  # O(1)
        v = None  # O(1)
        if a.startswith("--"):  # O(1)
            o, eq, val = a[2:].partition("=")  # O(len(a))
            if o in names or (len(o) >= 3 and any(n.startswith(o) for n in names)):  # O(1)
                v = val if eq else (args[i] if i < len(args) else "?")  # O(1)
                i += 0 if eq else 1  # O(1)
        elif a.startswith("-o") and sub in ("format-patch", "archive"):  # O(1)
            v = a[2:] if len(a) > 2 else (args[i] if i < len(args) else "?")  # O(1)
            i += 0 if len(a) > 2 else 1  # O(1)
        if v is not None:  # O(1)
            out.append(_join(base, v))  # O(len(v))
    return _uniq(out)  # O(len(out))


_GIT_CONFIG_WRITTEN = re.compile(r"(?:^|[^\w./-])git(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+config(?:\s|$)")  # O(1)
_UNKNOWN_TREE = "$GIT_WORK_TREE"  # a work tree the guard cannot name


def _is_abs(p: str) -> bool:  # O(1)
    return p.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", p) is not None  # O(1)


def _exists(cwd: str | None, base: str, p: str) -> bool:  # O(len(base) + len(p)) | does p exist below base (from cwd)?
    if "$" in base or "$" in p or base.startswith("~") or p.startswith("~"):  # an unknown folder: nothing to look at  # O(1)
        return False  # O(1)
    full = _join(base, p)  # O(len(base) + len(p))
    return os.path.exists(full if _is_abs(full) or cwd is None else os.path.join(cwd, full))  # O(1)


def _inside(cwd: str | None, top: str) -> bool:  # O(len(cwd) + len(top)) | does the shell sit in top (unknown: yes)?
    if cwd is None:  # O(1)
        return True  # O(1)
    a, b = os.path.realpath(cwd), os.path.realpath(top)  # O(1)
    return a == b or a.startswith(b.rstrip("/") + "/")  # O(1)


def _alias(words: list[str], i: int, al: str, cfg: dict[str, str], cwd: str | None, env, top, text, cflag: bool) -> list[str]:  # O(len(words))
    """A -c alias of a subcommand that is no git command, judged as what it runs (one level deep)."""
    rest = words[i:]  # O(len(words))
    if al.startswith("!"):  # git runs a shell alias at the work tree's top  # O(len(al))
        paths = _shell(al[1:] + "".join(" " + shlex.quote(a) for a in rest))  # O(len(al))
        if top and (cflag or _inside(cwd, top)):  # O(1)
            paths = [_join(top, p) for p in paths]  # O(len(paths))
        return paths  # O(len(paths))
    try:  # O(1)
        aw = shlex.split(al)  # O(len(al))
    except ValueError:  # O(1)
        return ["?"]  # O(1)
    if not aw or aw[0].lower() in {k[6:] for k in cfg if k.startswith("alias.")}:  # an alias of another alias: not followed  # O(len(cfg))
        return ["?"]  # O(len(cfg))
    return _git(words[:i - 1] + aw + rest, cwd, env, top, text)  # O(len(words))


def _git(words: list[str], cwd: str | None = None, env=None, top: str | None = None,
         text: str | None = None) -> list[str]:  # O(len(words))
    base, sub, i, cflag, wt, cfg = "", "", 1, False, None, {}  # O(1)
    unk = False  # a config the guard cannot read (include, --config-env, GIT_CONFIG*, a git dir, git config in the command)  # O(1)
    n = len(words)  # O(1)
    while i < n:  # O(len(words))
        a = words[i]  # O(1)
        if a in _GIT_VALOPTS:  # O(1)
            v = words[i + 1] if i + 1 < n else ""  # O(1)
            if a == "-C":  # O(1)
                base = _join(base, v) if base else v  # O(len(v))
                cflag = True  # O(1)
            elif a == "--work-tree":  # O(1)
                wt = v  # O(1)
                cflag = True  # O(1)
            elif a == "-c":  # O(1)
                k, _, val = v.partition("=")  # O(len(v))
                cfg[k.lower()] = val  # O(1)
                unk = unk or k.lower().startswith(("include.", "includeif."))  # O(1)
            elif a == "--config-env":  # O(1)
                unk = True  # O(1)
            elif a == "--git-dir":  # O(1)
                cflag = True  # O(1)
            i += 2  # O(1)
            continue  # O(1)
        if a.startswith("--work-tree="):  # O(1)
            wt = a.split("=", 1)[1]  # O(len(a))
            cflag = True  # O(1)
        elif a.startswith("--config-env="):  # O(1)
            unk = True  # O(1)
        elif a.startswith("--git-dir="):  # O(1)
            cflag = True  # O(1)
        elif a.startswith("-C") and len(a) > 2:  # O(1)
            base = _join(base, a[2:]) if base else a[2:]  # O(len(a))
            cflag = True  # O(1)
        elif a.startswith("-"):  # O(1)
            pass  # O(1)
        else:  # O(1)
            sub = a  # O(1)
            i += 1  # O(1)
            break  # O(1)
        i += 1  # O(1)
    if not sub:  # O(1)
        return []  # O(1)
    blob = text if text is not None else " ".join(words)  # O(len(blob))
    low = blob.lower()  # O(len(blob))
    unk = unk or "GIT_CONFIG" in blob or "GIT_DIR" in blob or "--git-dir" in low or _GIT_CONFIG_WRITTEN.search(low) is not None  # O(len(blob))
    env = env or {}  # O(1)
    if wt is None:  # not given on the command line: GIT_WORK_TREE (precise from env, else named elsewhere), core.worktree  # O(1)
        if "GIT_WORK_TREE" in env:  # O(1)
            wt = env["GIT_WORK_TREE"] or _UNKNOWN_TREE  # O(1)
        elif "GIT_WORK_TREE" in blob:  # O(1)
            wt = _UNKNOWN_TREE  # O(1)
        elif "core.worktree" in cfg:  # O(1)
            wt = cfg["core.worktree"]  # O(1)
        elif unk:  # O(1)
            wt = _UNKNOWN_TREE  # O(1)
    if wt is not None:  # O(1)
        if not wt or wt.startswith("~") or "$" in wt or "`" in wt:  # an unknown tree  # O(len(wt))
            base = _UNKNOWN_TREE  # O(1)
        else:  # O(1)
            base = wt if _is_abs(wt) or not base else _join(base, wt)  # O(len(wt))
    if sub not in _GIT_CMDS:  # O(1)
        al = [v for k, v in cfg.items() if k.startswith("alias.") and k[6:] == sub.lower()]  # O(len(cfg))
        if al:  # O(1)
            return _alias(words, i, al[-1], cfg, cwd, env, top, text, cflag)  # O(len(words))
        return ["?"] if unk else []  # an alias from a config this cannot read  # O(1)
    args = words[i:]  # O(len(words))
    paths: list[str] = []  # O(1)
    ops: list[str] = []  # O(1)
    dd, skip = False, False  # O(1)
    for a in args:  # the operands after the subcommand; -- ends the options  # O(len(args))
        if skip:  # O(1)
            skip = False  # O(1)
            continue  # O(1)
        if dd:  # O(1)
            paths.append(a)  # O(1)
        elif a == "--":  # O(1)
            dd = True  # O(1)
        elif a in _GIT_SKIP:  # O(1)
            skip = True  # O(1)
        elif not a.startswith("-"):  # O(1)
            ops.append(a)  # O(1)
    for a in args:  # O(len(args))
        if a == "--":  # O(1)
            break  # O(1)
        if a.startswith("--") and len(a) > 2 and "pathspec-from-file".startswith(a[2:].split("=", 1)[0]):  # O(len(a))
            return ["?"]  # O(1)
    root = base or "."  # O(1)

    def whole() -> list[str]:  # O(1)
        return [root if base else "."]  # O(1)

    if sub in ("apply", "am"):  # the patch may touch any file below the directory git runs in  # O(1)
        return whole()  # O(1)
    if sub in _GIT_OUT:  # a command that writes its output to a named file or folder  # O(len(args))
        return _git_out(sub, args, base)  # O(len(args))
    if sub == "stash":  # O(1)
        return whole() if ops and ops[0] in ("pop", "apply", "branch") else []  # O(1)
    if sub == "reset":  # O(1)
        for a in args:  # also shortened (--har); an unclear --m counts as --merge  # O(len(args))
            if a == "--":  # O(1)
                break  # O(1)
            if a.startswith("--") and len(a) > 2:  # O(1)
                o = a[2:].split("=", 1)[0]  # O(len(a))
                if any(w.startswith(o) for w in ("hard", "merge", "keep")):  # O(1)
                    return whole()  # O(1)
        return []  # O(1)
    if sub == "switch":  # O(1)
        return whole() if _git_flag(args, "f", "force", sub) or _git_flag(args, "", "discard-changes", sub) else []  # O(len(args))
    if sub == "checkout-index":  # O(1)
        pre = [_join(base, a.split("=", 1)[1]) for a in args if a.startswith("--prefix=")]  # files land under the prefix  # O(len(args))
        if _git_flag(args, "f", "force", sub) or _git_flag(args, "a", "all", sub):  # O(len(args))
            return pre or whole()  # O(1)
        return pre  # O(1)
    if sub == "read-tree":  # O(1)
        return whole() if _git_flag(args, "u", "", sub) else []  # O(len(args))
    if sub not in ("checkout", "restore", "rm", "mv", "clean"):  # O(1)
        return []  # O(1)
    if sub not in ("restore", "checkout") and _git_flag(args, "n", "dry-run", sub):  # O(len(args))
        return []  # O(1)
    if sub == "restore":  # O(1)
        if _git_flag(args, "S", "staged", sub) and not _git_flag(args, "W", "worktree", sub):  # O(len(args))
            return []  # O(1)
        paths = ops + paths  # O(len(ops))
    elif sub == "rm":  # O(1)
        if _git_flag(args, "", "cached", sub):  # O(len(args))
            return []  # O(1)
        paths = ops + paths  # O(len(ops))
    elif sub == "mv":  # O(1)
        paths = ops + paths  # O(len(ops))
    elif sub == "clean":  # O(1)
        paths = ops + paths or ["./?"]  # O(len(ops)) no path: any file below the directory, its own folder is no target
    else:  # checkout: without --, <tree-ish> <path>..., or one operand that names an existing path  # O(1)
        if _git_flag(args, "f", "force", sub):  # O(len(args))
            return whole()  # O(1)
        if not dd:  # O(1)
            if len(ops) >= 2:  # O(1)
                paths = ops[1:]  # O(len(ops))
            if ops and (_exists(cwd, base, ops[0]) or any(  # --ours/--theirs/--conflict take only paths
                    _git_flag([x], "", "ours", sub) or _git_flag([x], "", "theirs", sub)
                    or _git_flag([x], "", "conflict", sub) for x in args)):  # O(len(args))
                paths.append(ops[0])  # O(1)
        if _git_flag(args, "p", "patch", sub) and not paths:  # O(len(args))
            paths = ["."]  # O(1)
    out: list[str] = []  # O(1)
    for p in paths:  # O(len(paths))
        out.append("?" if p.startswith(":") else _join(base, p))  # pathspec magic  # O(len(p))
    return _uniq(out)  # O(len(out))


# ---------------------------------------------------------------- archives

_TAR_VAL = frozenset(
    "file files-from exclude exclude-from exclude-tag exclude-tag-under exclude-tag-all strip-components "
    "use-compress-program transform xform owner group mode mtime newer newer-mtime after-date format label suffix "
    "blocking-factor record-size tape-length info-script new-volume-script volno-file rsh-command rmt-command "
    "index-file checkpoint-action hole-detection level listed-incremental quoting-style quote-chars no-quote-chars "
    "sort starting-file to-command warning xattrs-include xattrs-exclude owner-map group-map pax-option options "
    "include newer-than uid gid uname gname passphrase older older-mtime older-than older-mtime-than "
    "newer-mtime-than sparse-version exclude-ignore exclude-ignore-recursive set-mtime-format".split()
)
_TAR_FLAG = frozenset(  # long options without a separate value (or with one only after =): the riskier reading
    "xattrs checkpoint incremental extract get directory cd absolute-names to-stdout verbose list create append "
    "update diff delete gzip gunzip bzip2 xz lzma lzip lzop zstd compress uncompress keep-old-files keep-newer-files "
    "overwrite no-overwrite-dir preserve-permissions same-permissions preserve-order same-order same-owner "
    "no-same-owner no-same-permissions numeric-owner one-file-system recursive dereference hard-dereference "
    "ignore-zeros ignore-failed-read totals utc sparse selinux no-selinux acls no-acls no-xattrs touch wildcards "
    "no-wildcards anchored no-anchored show-omitted-dirs show-transformed-names atime-preserve remove-files "
    "unlink-first skip-old-files overwrite-dir no-recursion null verify check-links interactive confirmation "
    "occurrence backup full-time exclude-vcs exclude-backups exclude-caches exclude-caches-all exclude-caches-under "
    "no-ignore-case ignore-case posix restrict help usage version".split()
)
_TAR_ALL = _TAR_VAL | _TAR_FLAG


def _tar(args: list[str]) -> list[str]:  # O(len(args) * |options|)
    x = absn = False  # O(1)
    d, explicit, first, dd = ".", False, True, False  # O(1)
    oq = ""  # O(1)
    members: list[tuple[str, str]] = []  # O(1)

    def cd(new: str) -> str:  # tar joins a relative -C onto the one before it  # O(len(new))
        if new.startswith("/") or re.match(r"^[A-Za-z]:[/\\]", new):  # O(1)
            return new  # O(1)
        return new if d == "." else d.rstrip("/") + "/" + new  # O(len(d) + len(new))

    for a in args:  # O(len(args))
        if oq:  # a value  # O(1)
            ch, oq = oq[0], oq[1:]  # O(1)
            if ch == "C":  # O(1)
                d, explicit = cd(a), True  # O(1)
            first = False  # O(1)
            continue  # O(1)
        r = ""  # O(1)
        if dd:  # O(1)
            members.append((d, a))  # O(1)
            continue  # O(1)
        if a == "--":  # O(1)
            dd = True  # O(1)
        elif a.startswith("--"):  # a long option, also shortened to a prefix; an unclear prefix is the riskier option  # O(1)
            o = a[2:].split("=", 1)[0]  # O(len(a))
            if "extract".startswith(o) or "get".startswith(o):  # O(1)
                x = True  # O(1)
            if "absolute-names".startswith(o):  # O(1)
                absn = True  # O(1)
            if "to-stdout".startswith(o) and len(o) >= 4:  # --to and --to- may be --to-command  # O(1)
                return []  # O(1)
            if "directory".startswith(o) or "cd".startswith(o):  # --cd: bsdtar's name for -C  # O(1)
                if "=" in a:  # O(1)
                    d, explicit = cd(a.split("=", 1)[1]), True  # O(len(a))
                else:  # O(1)
                    oq = "C"  # O(1)
            elif "=" not in a:  # --file X, --older-than D: the next word is the value, no member name  # O(1)
                names = [n for n in _TAR_ALL if n.startswith(o)]  # O(|options|)
                if o in _TAR_ALL:  # O(1)
                    names = [o]  # O(1)
                if names and all(n in _TAR_VAL for n in names):  # O(len(names))
                    oq = "V"  # O(1)
        elif a.startswith("-") and len(a) > 1:  # O(1)
            r = a[1:]  # O(1)
        elif first and a.isalpha() and a.isascii():  # old style: tar xf  # O(len(a))
            r = a  # O(1)
        else:  # O(1)
            members.append((d, a))  # O(1)
        for i, ch in enumerate(r):  # O(len(r))
            if ch == "x":  # O(1)
                x = True  # O(1)
            elif ch == "P":  # O(1)
                absn = True  # O(1)
            elif ch == "O":  # members go to stdout  # O(1)
                return []  # O(1)
            elif ch in "CfTXbKNgVHLFI":  # O(1)
                if a.startswith("-"):  # O(1)
                    rest = r[i + 1:]  # O(len(r))
                    if rest:  # O(1)
                        if ch == "C":  # O(1)
                            d, explicit = cd(rest), True  # O(len(rest))
                    else:  # O(1)
                        oq = ch  # O(1)
                    break  # O(1)
                oq += ch  # O(1)
        first = False  # O(1)
    if not x:  # O(1)
        return []  # O(1)
    if absn:  # absolute member names land anywhere  # O(1)
        return ["?"]  # O(1)
    out = [_join(md, m) for md, m in members]  # a member lands in the directory in force, the shell's by default  # O(len(members))
    if explicit or not members:  # O(1)
        out.append(_dirp(d))  # O(1)
    return _uniq(out)  # O(len(out))


def _unzip(args: list[str]) -> list[str]:  # O(sum of len(args))
    d, oq, absn = ".", "", False  # O(1)
    for a in args:  # O(len(args))
        if oq:  # O(1)
            if oq == "C":  # O(1)
                d = a  # O(1)
            oq = ""  # O(1)
            continue  # O(1)
        if a.startswith("--") or not a.startswith("-") or len(a) < 2:  # O(1)
            continue  # O(1)
        r = a[1:]  # O(1)
        for i, ch in enumerate(r):  # O(len(r))
            if ch in "ltvZzpc":  # listing, testing, piping: nothing is written  # O(1)
                return []  # O(1)
            if ch == ":":  # O(1)
                absn = True  # O(1)
            elif ch == "d":  # O(1)
                if i + 1 < len(r):  # O(1)
                    d = r[i + 1:]  # O(len(r))
                else:  # O(1)
                    oq = "C"  # O(1)
                break  # O(1)
            elif ch == "P":  # -P PASSWORD  # O(1)
                if i + 1 >= len(r):  # O(1)
                    oq = "P"  # O(1)
                break  # O(1)
            elif ch == "x":  # the member names to leave out follow  # O(1)
                break  # O(1)
    return ["?"] if absn else [_dirp(d)]  # O(1)


def _sevenz(args: list[str]) -> list[str]:  # O(len(args))
    sub = next((a.lower() for a in args if not a.startswith("-")), "")  # O(len(args))
    if sub not in ("x", "e"):  # O(1)
        return []  # O(1)
    d = "."  # O(1)
    for a in args:  # O(len(args))
        if a.startswith("-o") and len(a) > 2:  # -ooutdir (-ao... is the overwrite mode)  # O(1)
            d = a[2:]  # O(len(a))
    return [_dirp(d)]  # O(1)


def _cpio(args: list[str]) -> list[str]:  # O(len(args))
    for a in args:  # O(len(args))
        if a in ("--extract", "--pass-through"):  # O(1)
            return ["?"]  # O(1)
        if a.startswith("-") and not a.startswith("--"):  # O(1)
            for ch in a[1:]:  # O(len(a))
                if ch in "HFIORCEM":  # an option with a value ends the cluster  # O(1)
                    break  # O(1)
                if ch in "ip":  # O(1)
                    return ["?"]  # O(1)
    return []  # O(1)


# ---------------------------------------------------------------- interpreter code

class _Name(str):  # O(1) | an argument that stands for several literals (a name assigned or looped over several)
    alts: list[str] = []  # O(1)


_NAMES: list[dict[str, list[str]]] = [{}]  # O(1) | the names of the code in hand that are assigned only literals
_ASSIGN = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*([-+*/%|&^@]|//|\*\*|<<|>>)?=(?![=>])\s*")  # O(1)
_FOR = re.compile(r"(?<![\w.])for\s+([A-Za-z_][\w\s,()]*?)\s+in\s+")  # O(1)
_UNK = "\x00"  # an unknown piece inside a composed path
_PATH_CTORS = frozenset({"Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath"})
_JOINS = frozenset({"os.path.join", "posixpath.join", "ntpath.join", "path.join", "join"})
_IDENT = re.compile(r"[A-Za-z_]\w*")
_STR_OPEN = re.compile(r"([rRbBuUfF]{0,2})('''|\"\"\"|'|\")")


def _final(v: str) -> str:  # O(len(v)) | an unknown piece becomes a `?` component below an absolute literal prefix, else all is unknown
    if _UNK not in v:  # O(len(v))
        return v  # O(1)
    pre = v[:v.index(_UNK)]  # O(len(v))
    cut = max(pre.rfind("/"), pre.rfind("\\"))  # O(len(pre))
    return pre[:cut + 1] + "?" if pre and _is_abs(pre) and cut >= 0 else "?"  # O(len(pre))


def _scan_close(code: str, i: int) -> int:  # O(len(code)) | index of the bracket closing the one at i (len(code) if none)
    depth, q, n = 0, "", len(code)  # O(1)
    while i < n:  # O(len(code))
        c = code[i]  # O(1)
        if q:  # O(1)
            if c == "\\":  # O(1)
                i += 1  # O(1)
            elif c == q:  # O(1)
                q = ""  # O(1)
        elif c in "'\"":  # O(1)
            q = c  # O(1)
        elif c in "([{":  # O(1)
            depth += 1  # O(1)
        elif c in ")]}":  # O(1)
            depth -= 1  # O(1)
            if depth == 0:  # O(1)
                return i  # O(1)
        i += 1  # O(1)
    return n  # O(1)


def _stmt_end(code: str, i: int) -> int:  # O(len(code)) | end of the statement or argument starting at i
    depth, q, n = 0, "", len(code)  # O(1)
    while i < n:  # O(len(code))
        c = code[i]  # O(1)
        if q:  # O(1)
            if c == "\\":  # O(1)
                i += 1  # O(1)
            elif c == q:  # O(1)
                q = ""  # O(1)
        elif c in "'\"":  # O(1)
            q = c  # O(1)
        elif c in "([{":  # O(1)
            depth += 1  # O(1)
        elif c in ")]}":  # O(1)
            if depth == 0:  # O(1)
                return i  # O(1)
            depth -= 1  # O(1)
        elif depth == 0 and c in ";\n,":  # O(1)
            return i  # O(1)
        i += 1  # O(1)
    return n  # O(1)


def _join1(x: str, y: str) -> str:  # O(len(x) + len(y)) | os.path.join / Path division of two literals
    if _UNK in x:  # an unknown piece swallows what follows  # O(len(x))
        return x  # O(1)
    if _is_abs(y) or not x:  # an absolute part starts over  # O(1)
        return y  # O(1)
    return x + y if x.endswith("/") else x + "/" + y  # O(len(x) + len(y))


class _Comp:  # O(len(text)) | a Python path expression: literals, f-strings, names, Path(...), os.path.join(...), `/`
    def __init__(self, s: str, names: dict[str, list[str]]):  # O(1)
        self.s, self.i, self.names = s, 0, names  # O(1)

    def ws(self) -> None:  # O(len(s))
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n":  # O(len(s))
            self.i += 1  # O(1)

    def top(self, atom_only: bool) -> list[str] | None:  # O(len(s))
        r = self.term() if atom_only else self.expr()  # O(len(s))
        self.ws()  # O(len(s))
        return r if r is not None and self.i == len(self.s) else None  # O(1)

    def expr(self) -> list[str] | None:  # O(len(s))
        left = self.term()  # O(len(s))
        while left is not None:  # O(len(s))
            self.ws()  # O(len(s))
            c = self.s[self.i:self.i + 1]  # O(1)
            if c == "/" and self.s[self.i:self.i + 2] != "//":  # a string `+` is not followed: the old guard did not  # O(1)
                self.i += 1  # O(1)
                right = self.term()  # O(len(s))
                if right is None:  # O(1)
                    return None  # O(1)
                left = [_join1(x, y) for x in left for y in right][:64]  # O(64)
            else:  # O(1)
                break  # O(1)
        return left  # O(1)

    def term(self) -> list[str] | None:  # O(len(s)) | an atom and its attribute, call and subscript tails
        self.ws()  # O(len(s))
        v = self.atom()  # O(len(s))
        while v is not None:  # O(len(s))
            c = self.s[self.i:self.i + 1]  # O(1)
            if c == ".":  # O(1)
                self.i += 1  # O(1)
                m = _IDENT.match(self.s, self.i)  # O(1)
                if not m:  # O(1)
                    return None  # O(1)
                self.i = m.end()  # O(1)
                if self.s[self.i:self.i + 1] == "(":  # O(1)
                    if self.args() is None:  # O(len(s))
                        return None  # O(1)
                    if m.group(0) not in ("resolve", "absolute", "as_posix"):  # O(1)
                        v = [_UNK]  # O(1)
                else:  # O(1)
                    v = [_UNK]  # O(1)
            elif c == "[":  # O(1)
                self.i = min(_scan_close(self.s, self.i) + 1, len(self.s))  # O(len(s))
                v = [_UNK]  # O(1)
            else:  # O(1)
                break  # O(1)
        return v  # O(1)

    def args(self) -> list[list[str]] | None:  # O(len(s)) | the positional arguments of the call at self.i (a `(`)
        self.i += 1  # O(1)
        out: list[list[str]] = []  # O(1)
        while True:  # O(len(s))
            self.ws()  # O(len(s))
            if self.s[self.i:self.i + 1] == ")":  # O(1)
                self.i += 1  # O(1)
                return out  # O(1)
            kw = re.match(r"[A-Za-z_]\w*\s*=(?!=)", self.s[self.i:self.i + 80])  # O(1)
            if kw:  # O(1)
                self.i += kw.end()  # O(1)
            v = self.expr()  # O(len(s))
            if v is None:  # O(1)
                return None  # O(1)
            if not kw:  # O(1)
                out.append(v)  # O(1)
            self.ws()  # O(len(s))
            if self.s[self.i:self.i + 1] == ",":  # O(1)
                self.i += 1  # O(1)
            elif self.s[self.i:self.i + 1] != ")":  # O(1)
                return None  # O(1)

    def atom(self) -> list[str] | None:  # O(len(s))
        s, i = self.s, self.i  # O(1)
        c = s[i:i + 1]  # O(1)
        if c == "(":  # O(1)
            self.i += 1  # O(1)
            v = self.expr()  # O(len(s))
            self.ws()  # O(len(s))
            if v is None or self.s[self.i:self.i + 1] != ")":  # a tuple or something else  # O(1)
                return None  # O(1)
            self.i += 1  # O(1)
            return v  # O(1)
        sm = _STR_OPEN.match(s, i)  # O(1)
        if sm:  # O(1)
            return self.string(sm)  # O(len(s))
        m = _IDENT.match(s, i)  # O(1)
        if not m:  # O(1)
            return None  # O(1)
        j = m.end()  # O(1)
        while True:  # a dotted name  # O(len(s))
            d = re.compile(r"\.[A-Za-z_]\w*").match(s, j)  # O(1)
            if not d:  # O(1)
                break  # O(1)
            j = d.end()  # O(1)
        name = s[i:j]  # O(1)
        self.i = j  # O(1)
        if s[j:j + 1] != "(":  # O(1)
            return list(self.names[name])[:64] if name in self.names else [_UNK]  # O(64)
        args = self.args()  # O(len(s))
        if args is None:  # O(1)
            return None  # O(1)
        last = name.rsplit(".", 1)[-1]  # O(1)
        if last in _PATH_CTORS or name in _JOINS:  # O(1)
            acc = args[0] if args else ["."]  # O(1)
            for a in args[1:]:  # O(len(args))
                acc = [_join1(x, y) for x in acc for y in a][:64]  # O(64)
            return acc  # O(1)
        if name in ("str", "os.fspath", "fspath") and len(args) == 1:  # O(1)
            return args[0]  # O(1)
        return [_UNK]  # O(1)

    def string(self, sm: re.Match) -> list[str] | None:  # O(len(s)) | a string or f-string literal
        s = self.s  # O(1)
        pre, q = sm.group(1).lower(), sm.group(2)  # O(1)
        j = sm.end()  # O(1)
        start = j  # O(1)
        while j < len(s) and not s.startswith(q, j):  # O(len(s))
            j += 2 if s[j] == "\\" else 1  # O(1)
        if j >= len(s):  # unterminated  # O(1)
            return None  # O(1)
        body = s[start:j]  # O(len(s))
        self.i = j + len(q)  # O(1)
        if "f" not in pre:  # O(1)
            return [body if "r" in pre else re.sub(r"\\(.)", r"\1", body, flags=re.S)]  # O(len(body))
        out = [""]  # O(1)
        k = 0  # O(1)
        while k < len(body):  # O(len(body))
            c = body[k]  # O(1)
            if c in "{}" and body[k + 1:k + 2] == c:  # O(1)
                piece, k = [c], k + 2  # O(1)
            elif c == "{":  # O(1)
                e = _scan_close(body, k)  # O(len(body))
                expr = body[k + 1:e].strip()  # O(len(body))
                piece = list(self.names[expr])[:64] if _IDENT.fullmatch(expr) and expr in self.names else [_UNK]  # O(64)
                k = e + 1  # O(1)
            else:  # O(1)
                m = re.compile(r"[^{}\\]+|\\.?", re.S).match(body, k)  # O(len(body))
                text = m.group(0) if m else c  # O(1)
                k += len(text) if m else 1  # O(1)
                piece = [text if "r" in pre else re.sub(r"\\(.)", r"\1", text, flags=re.S)]  # O(len(text))
            out = [x + y for x in out for y in piece][:64]  # O(64)
        return out  # O(64)


def _compose_raw(text: str, names: dict[str, list[str]], atom_only: bool = False) -> list[str] | None:  # O(len(text))
    """The values a Python path expression can take (an unknown piece is _UNK), None when it is not understood."""
    return _Comp(text.strip(), names).top(atom_only)  # O(len(text))


def _compose(text: str, names: dict[str, list[str]], atom_only: bool = False) -> list[str] | None:  # O(len(text))
    """_compose_raw with each value finalised: "/tmp/s/?" for an unknown piece below an absolute prefix, else "?"."""
    r = _compose_raw(text, names, atom_only)  # O(len(text))
    return _uniq([_final(v) for v in r]) if r is not None else None  # O(len(r))


def _split_top(text: str) -> list[str]:  # O(len(text)) | the top-level comma-separated parts
    out, q, depth, cur = [], "", 0, []  # O(1)
    i = 0  # O(1)
    while i < len(text):  # O(len(text))
        c = text[i]  # O(1)
        if q:  # O(1)
            if c == "\\":  # O(1)
                cur.append(c)  # O(1)
                i += 1  # O(1)
                c = text[i] if i < len(text) else ""  # O(1)
            elif c == q:  # O(1)
                q = ""  # O(1)
        elif c in "'\"":  # O(1)
            q = c  # O(1)
        elif c in "([{":  # O(1)
            depth += 1  # O(1)
        elif c in ")]}":  # O(1)
            depth -= 1  # O(1)
        elif c == "," and depth == 0:  # O(1)
            out.append("".join(cur))  # O(len(text))
            cur = []  # O(1)
            i += 1  # O(1)
            continue  # O(1)
        cur.append(c)  # O(1)
        i += 1  # O(1)
    if "".join(cur).strip():  # O(len(text))
        out.append("".join(cur))  # O(len(text))
    return out  # O(len(out))


def _assigned(code: str, lang: str) -> dict[str, list[str]]:  # O(len(code)) | name -> its literals; any other assignment drops it
    lits: dict[str, list[str]] = {}  # O(1)
    bad: set[str] = set()  # O(1)
    events = [(m.start(), m) for m in _ASSIGN.finditer(code)]  # O(len(code))
    events += [(m.start(), m) for m in _FOR.finditer(code)] if lang == "py" else []  # O(len(code))
    events.sort(key=lambda e: e[0])  # O(events * log events)
    for _, m in events:  # O(events)
        known = {k: v for k, v in lits.items() if k not in bad}  # O(len(lits))
        if m.re is _FOR:  # for NAME in (literal, ...): the name takes every value  # O(1)
            names = _IDENT.findall(m.group(1))  # O(1)
            vals = None  # O(1)
            if len(names) == 1 and _IDENT.fullmatch(m.group(1).strip()) and code[m.end():m.end() + 1] in ("[", "("):  # O(1)
                close = _scan_close(code, m.end())  # O(len(code))
                parts = _split_top(code[m.end() + 1:close])  # O(len(code))
                raws = [_compose_raw(x, known) for x in parts]  # O(len(parts))
                if parts and all(r is not None and all(_UNK not in v for v in r) for r in raws):  # O(len(parts))
                    vals = [v for r in raws for v in r]  # type: ignore[union-attr]  # O(len(parts))
            if vals is None:  # O(1)
                bad.update(names)  # O(1)
            else:  # O(1)
                lits.setdefault(names[0], []).extend(v for v in vals if v not in lits.get(names[0], []))  # O(len(vals))
            continue  # O(1)
        name = m.group(1)  # O(1)
        pp = re.compile(r"(?:pathlib\.)?(?:Path|PurePath)\(").match(code, m.end()) if lang == "py" else None  # O(1)
        pm = _LIT.match(code, pp.end() if pp else m.end())  # O(1)
        vals = None  # O(1)
        if pm and not m.group(2):  # O(1)
            end = pm.end()  # O(1)
            if pp:  # Path('lit') then the closing parenthesis  # O(1)
                cm = re.compile(r"[ \t]*\)").match(code, end)  # O(1)
                end = cm.end() if cm else -1  # O(1)
            tail = code[end:].lstrip(" \t") if end >= 0 else "x"  # O(len(code))
            if not tail or tail[0] in ";\n,)":  # the statement ends here  # O(1)
                vals = [_unq(pm, lang)]  # type: ignore[list-item]  # O(1)
        if vals is None and lang == "py" and not m.group(2):  # a composition of literals and known names  # O(len(code))
            raw = _compose_raw(code[m.end():_stmt_end(code, m.end())], known)  # O(len(code))
            if raw is not None and all(_UNK not in v for v in raw):  # O(len(raw))
                vals = raw  # O(1)
        if vals is None or None in vals:  # O(1)
            bad.add(name)  # O(1)
        else:  # O(1)
            lits.setdefault(name, []).extend(v for v in vals if v not in lits.get(name, []))  # O(len(vals))
    return {k: v for k, v in lits.items() if k not in bad}  # O(len(lits))


# A call's arguments are parsed from the literal code: (keyword or None, literal text or None when not literal).
Arg = tuple  # O(1)


def _parse_args(code: str, pos: int, lang: str, bare: bool) -> tuple[list[Arg], int]:  # O(len(code) - pos)
    n = len(code)  # O(1)
    i = pos  # O(1)
    while i < n and code[i] in " \t":  # O(n)
        i += 1  # O(1)
    paren = i < n and code[i] == "("  # O(1)
    if paren:  # O(1)
        i += 1  # O(1)
    elif not bare:  # O(1)
        return [], pos  # O(1)
    args: list[Arg] = []  # O(1)

    def at_end(j: int) -> bool:  # O(1)
        if j >= n:  # O(1)
            return True  # O(1)
        return code[j] == ")" if paren else code[j] in ";\n"  # O(1)

    while True:  # O(n)
        while i < n and (code[i] in " \t\r\n" if paren else code[i] in " \t"):  # O(n)
            i += 1  # O(1)
        if at_end(i):  # O(1)
            return args, min(i + 1, n)  # O(1)
        key = None  # O(1)
        m = re.match(r"([A-Za-z_]\w*)\s*(?:=(?!=)|:(?!:))\s*", code[i:i + 80])  # keyword argument  # O(1)
        if m and lang != "js":  # O(1)
            key, i = m.group(1), i + m.end()  # O(1)
        val: str | None = None  # O(1)
        start = i  # O(1)
        j = i  # O(1)
        pm = re.match(r"[rRbBuU]{0,2}(?=['\"])", code[i:i + 3]) if lang == "py" else None  # O(1)
        if pm:  # O(1)
            j = i + pm.end()  # O(1)
        if j < n and code[j] in "'\"`":  # O(1)
            q = code[j]  # O(1)
            k, buf = j + 1, []  # O(1)
            while k < n and code[k] != q:  # O(n)
                if code[k] == "\\" and k + 1 < n:  # O(1)
                    buf.append(code[k + 1])  # O(1)
                    k += 2  # O(1)
                else:  # O(1)
                    buf.append(code[k])  # O(1)
                    k += 1  # O(1)
            text = "".join(buf)  # O(len(buf))
            k += 1  # O(1)
            e = k  # O(1)
            while e < n and code[e] in " \t":  # O(n)
                e += 1  # O(1)
            dyn = (q == "`" and "${" in text) or (q == '"' and lang == "php" and "$" in text) or (
                q == '"' and lang == "pl" and ("$" in text or "@" in text)) or (
                q == '"' and lang == "rb" and "#{" in text)  # O(len(text))
            if (e >= n or code[e] == "," or at_end(e)) and not dyn:  # O(1)
                val, i = text, k  # O(1)
        if val is None:  # not a literal: skip to the next top-level comma  # O(1)
            depth, q = 0, ""  # O(1)
            while i < n:  # O(n)
                c = code[i]  # O(1)
                if q:  # O(1)
                    if c == "\\":  # O(1)
                        i += 1  # O(1)
                    elif c == q:  # O(1)
                        q = ""  # O(1)
                elif c in "'\"`":  # O(1)
                    q = c  # O(1)
                elif c in "([{":  # O(1)
                    depth += 1  # O(1)
                elif c in ")]}":  # O(1)
                    if depth == 0:  # O(1)
                        break  # O(1)
                    depth -= 1  # O(1)
                elif depth == 0 and (c == "," or (not paren and c in ";\n")):  # O(1)
                    break  # O(1)
                i += 1  # O(1)
        if val is None and lang != "py" and _NAMES[0]:  # a bare name: the caller may resolve it to the literals it was assigned  # O(n)
            bare = code[start:i].strip()  # O(n)
            if bare in _NAMES[0]:  # O(1)
                val = _Name(bare)  # O(1)
                val.alts = _NAMES[0][bare]  # O(1)
        if val is None and lang == "py":  # a composition of literals and names: the path, or one with a `?` component  # O(n)
            alts = _compose(code[start:i], _NAMES[0])  # O(n)
            if alts and len(alts) == 1:  # O(1)
                val = None if alts[0] == "?" else alts[0]  # O(1)
            elif alts:  # O(1)
                val = _Name(code[start:i].strip())  # O(1)
                val.alts = alts  # O(1)
        args.append((key, val))  # O(1)
        while i < n and code[i] in " \t":  # O(n)
            i += 1  # O(1)
        if i < n and code[i] == ",":  # O(1)
            i += 1  # O(1)
            continue  # O(1)
        return args, min(i + 1, n) if paren else i  # O(1)


def _pos(args: list[Arg]) -> list:  # O(len(args))
    return [v for k, v in args if k is None]  # O(len(args))


def _t(v: str | None) -> str:  # O(1)
    return "?" if not v else v  # O(1)


def _a_arg(i: int):  # O(1)
    def f(args: list[Arg], raw: str) -> list[str]:  # O(len(args))
        p = _pos(args)  # O(len(args))
        return [_t(p[i])] if i < len(p) else ["?"]  # O(1)
    return f  # O(1)


def _a_last(args: list[Arg], raw: str) -> list[str]:  # O(len(args))
    p = _pos(args)  # O(len(args))
    return [_t(p[-1])] if len(p) >= 2 else ["?"]  # O(1)


def _a_all(args: list[Arg], raw: str) -> list[str]:  # O(len(args))
    p = _pos(args)  # O(len(args))
    return [_t(v) for v in p] if p else ["?"]  # O(len(p))


def _a_open(pi: int, mi: int, pk: str = "file", mk: str = "mode"):  # O(1)
    def f(args: list[Arg], raw: str) -> list[str]:  # O(len(args))
        p = _pos(args)  # O(len(args))
        kw = {k: v for k, v in args if k}  # O(len(args))
        mode = p[mi] if mi < len(p) else kw.get(mk, "")  # O(1)
        path = p[pi] if pi < len(p) else kw.get(pk)  # O(1)
        if mode is None or any(c in mode for c in "wax+"):  # a mode that is not literal counts as a write  # O(len(mode))
            return [_t(path)]  # O(1)
        return []  # O(1)
    return f  # O(1)


def _a_osopen(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
    if re.search(r"O_WRONLY|O_RDWR|O_CREAT|O_APPEND|O_TRUNC", raw):  # O(len(raw))
        return [_t((_pos(args) or [None])[0])]  # O(1)
    return []  # O(1)


# ---- a shell command inside interpreter code (os.system, subprocess, child_process, system, backticks)

_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "fish"})
_PSHELLS = frozenset({"powershell", "pwsh"})
_WRAP = frozenset({"env", "sudo", "doas", "nohup", "time", "command", "exec", "nice", "ionice", "stdbuf", "setsid",
                   "builtin", "timeout", "chroot", "unbuffer", "caffeinate"})
_FIND_W = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"})
_depth = [0]
_LIT = re.compile(r"""[ \t\r\n]*(?:[rRbBuU]{0,2}'((?:[^'\\]|\\.)*)'|[rRbBuU]{0,2}"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)""",
                  re.S)  # O(1)


def _unq(m: re.Match, lang: str) -> str | None:  # O(len(text)) | a literal's text, None when it interpolates
    text = next(g for g in m.groups() if g is not None)  # O(1)
    q = m.group(0).lstrip(" \t\r\n").rstrip()[-1]  # O(1)
    if (q == "`" and "${" in text) or (q == '"' and lang in ("php", "pl") and ("$" in text or "@" in text)) or (
            q == '"' and lang == "rb" and "#{" in text):  # O(len(text))
        return None  # O(1)
    return re.sub(r"\\(.)", r"\1", text, flags=re.S)  # O(len(text))


def _cmd_words(raw: str, lang: str) -> list[str] | None:  # O(len(raw)) | the literal command words, None when unknown
    s = raw.lstrip(" \t\r\n")  # O(len(raw))
    if s.startswith("("):  # O(1)
        s = s[1:]  # O(len(raw))
    words: list[str] = []  # O(1)
    while True:  # O(len(raw))
        s = s.lstrip(" \t\r\n")  # O(len(s))
        if not s or s[0] in ");":  # O(1)
            break  # O(1)
        if s[0] == "[":  # a list of literals: the argv  # O(1)
            j = s.find("]")  # O(len(s))
            if j < 0:  # O(1)
                return None  # O(1)
            inner, s = s[1:j], s[j + 1:]  # O(len(s))
            while inner.strip():  # O(len(inner))
                m = _LIT.match(inner)  # O(len(inner))
                v = _unq(m, lang) if m else None  # O(len(inner))
                if v is None:  # O(1)
                    return None  # O(1)
                words.append(v)  # O(1)
                inner = inner[m.end():].lstrip(" \t\r\n")  # O(len(inner))
                if inner.startswith(","):  # O(1)
                    inner = inner[1:]  # O(len(inner))
                elif inner:  # O(1)
                    return None  # O(1)
        else:  # O(1)
            m = _LIT.match(s)  # O(len(s))
            nxt = s[m.end():].lstrip(" \t") if m else ""  # O(len(s))
            if m and (not nxt or nxt[0] in ",);\n"):  # O(1)
                v = _unq(m, lang)  # O(len(s))
                if v is None:  # O(1)
                    return None  # O(1)
                words.append(v)  # O(1)
                s = s[m.end():]  # O(len(s))
            elif words and re.match(r"\{|\w+\s*(?:=(?!=)|:(?!:))|function\b|async\b|\(|\w+\s*=>|\)", s):  # options  # O(1)
                break  # O(1)
            else:  # O(1)
                return None  # O(1)
        s = s.lstrip(" \t")  # O(len(s))
        if s.startswith(","):  # O(1)
            s = s[1:]  # O(len(s))
        else:  # O(1)
            break  # O(1)
    return words or None  # O(1)


def _known(w: str) -> bool:  # O(len(w))
    c = _cmd(w)  # O(len(w))
    return (c in guard_files.COMMANDS or c in COMMANDS or c in _SHELLS or c in _PSHELLS or c in ("find", "xargs", "eval")
            or _PY.match(c) is not None)  # O(1)


def _shell(text: str) -> list[str]:  # O(len(text) * |commands|) | the paths shell text writes
    out: list[str] = []  # O(1)
    for seg in guard_lex.split(text):  # O(len(text))
        words = ["?" if d else w for w, d in zip(seg.words, seg.dyn)]  # O(w)
        if words and seg.dyn[0]:  # a command that is not literal  # O(1)
            out.append("?")  # O(1)
        out.extend(_argv(words))  # O(w)
        for r in seg.redirects:  # O(redirects)
            if r.op.startswith(("<<", "<")) and r.op != "<>":  # O(1)
                continue  # O(1)
            if r.op == ">&" and (r.target.isdigit() or r.target == "-"):  # an fd duplicate  # O(1)
                continue  # O(1)
            t = r.target  # O(1)
            if any(c in t for c in "$`") or t.startswith("~"):  # O(len(t))
                out.append("?")  # O(1)
            elif guard_files._real(t):  # O(len(t))
                out.append(t)  # O(1)
        for body in list(seg.bodies) + ([seg.subshell] if seg.subshell else []):  # O(bodies)
            out.extend(_shell(body))  # O(len(body))
    return _uniq(out)  # O(len(out))


def _argv(words: list[str]) -> list[str]:  # O(len(words) * |options|) | the paths one command (decoded words) writes
    if not words:  # O(1)
        return []  # O(1)
    k = 0  # O(1)
    if _cmd(words[0]) in _WRAP or re.match(r"[A-Za-z_]\w*=", words[0]):  # skip a wrapper and its options  # O(1)
        k = next((i for i in range(1, len(words)) if _known(words[i]) and not words[i].startswith("-")), len(words))  # O(w)
        if k == len(words):  # O(1)
            return []  # O(1)
    w = words[k:]  # O(w)
    c = _cmd(w[0])  # O(1)
    if c == "xargs" or (c == "find" and any(a in _FIND_W for a in w)):  # O(w)
        return ["?"]  # O(1)
    if c == "eval":  # O(1)
        return _shell(" ".join(w[1:]))  # O(w)
    if c in _SHELLS or c in _PSHELLS:  # O(1)
        for i, a in enumerate(w[1:], 1):  # O(w)
            if a.lower() in ("-c", "-command", "-lc", "-ec", "-ic", "-cl") and i + 1 < len(w):  # O(1)
                return _shell(w[i + 1])  # O(len(w[i + 1]))
        return []  # O(1)
    out: list[str] = []  # O(1)
    if c in guard_files.COMMANDS:  # O(1)
        out.extend(guard_files.targets(w))  # O(w)
    out.extend(_targets(w))  # O(w)
    return _uniq(out)  # O(len(out))


def _a_sh(args: list[Arg], raw: str, lang: str = "py") -> list[str]:  # O(len(raw)) | os.system, subprocess.run, ...
    words = _cmd_words(raw, lang)  # O(len(raw))
    if words is None or _depth[0] >= 4:  # O(1)
        return ["?"]  # O(1)
    _depth[0] += 1  # O(1)
    try:  # O(1)
        return _shell(words[0]) if len(words) == 1 else _argv(words)  # O(len(raw))
    finally:  # O(1)
        _depth[0] -= 1  # O(1)


def _a_sh_rb(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
    return _a_sh(args, raw, "rb")  # O(len(raw))


def _a_sh_php(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
    return _a_sh(args, raw, "php")  # O(len(raw))


def _a_sh_pl(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
    return _a_sh(args, raw, "pl")  # O(len(raw))


def _a_sh_js(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
    return _a_sh(args, raw, "js")  # O(len(raw))


def _a_unknown(args: list[Arg], raw: str) -> list[str]:  # O(1) | a call that runs a program the code names indirectly
    return ["?"]  # O(1)


def _a_tick(lang: str):  # O(1) | a backtick or %x command: its text is shell
    def f(args: list[Arg], raw: str) -> list[str]:  # O(len(raw))
        text = raw[1:-1] if raw[:1] == "`" and raw[-1:] == "`" else raw  # O(1)
        if "#{" in text or "${" in text or "$(" in text and lang != "rb":  # O(len(text))
            return ["?"]  # O(1)
        return _shell(text) if _depth[0] < 4 else ["?"]  # O(len(text))
    return f  # O(1)


def _a_perl_open(args: list[Arg], raw: str) -> list[str]:  # O(len(args)) | open(FH, '>f'), open(FH, '>', 'f')
    p = _pos(args)  # O(len(args))
    if len(p) >= 3:  # O(1)
        mode, path = p[1], p[2]  # O(1)
        if mode is None or any(c in mode for c in ">+|"):  # O(len(mode))
            return [_t(path)] if mode is None or "|" not in mode else ["?"]  # O(1)
        return []  # O(1)
    if len(p) == 2:  # O(1)
        spec = p[1]  # O(1)
        if spec is None:  # O(1)
            return ["?"]  # O(1)
        spec = spec.strip()  # O(len(spec))
        if "|" in spec:  # a pipe to or from a command  # O(len(spec))
            return ["?"]  # O(1)
        if spec[:1] in (">", "+"):  # O(1)
            return [spec.lstrip(">+<& \t") or "?"]  # O(len(spec))
        return []  # O(1)
    return ["?"] if p and None in p else []  # O(1)


_PYP = r"(?<![\w.])(?:(?:shutil|os|os\.path|pathlib)\.)?"
_NODE_FS = (r"(?:(?<![\w$.])|\b(?:fs|fsp|promises|fse|fsExtra)\.|"
            r"require\(\s*['\"](?:node:)?(?:fs|fs/promises|fs-extra)['\"]\s*\)\.)")
_PHP = r"(?<![\w$>:.])"
_RB_FU = r"(?<![\w.])(?:FileUtils|Fileutils)(?:\.|::)"

_CALLS: dict[str, list[tuple[str, object]]] = {
    "py": [
        (r"(?<![\w.])open\s*\(", _a_open(0, 1)),
        (r"(?<![\w$])(?:\w+\.)*(?:ZipFile|TarFile)\s*\(", _a_open(0, 1)),
        (r"\bos\.open\s*\(", _a_osopen),
        (_PYP + r"(?:copy|copy2|copyfile|copytree|move|rename|renames|replace|link|symlink)\s*\(", _a_arg(1)),
        (r"(?<![\w])(?:\w+\.)*(?:copyfile|copy2|copytree)\s*\(", _a_arg(1)),
        (_PYP + r"(?:remove|removedirs|unlink|rmdir|rmtree|truncate)\s*\(", _a_arg(0)),
        (r"(?<![\w.])(?:os\.)?(?:system|popen)\s*\(", _a_sh),
        (r"(?<![\w.])(?:subprocess\.)?(?:run|call|check_call|check_output|Popen|getoutput|getstatusoutput)\s*\(",
         lambda a, r: _a_sh(a, r) if re.match(r"\s*\(?\s*(?:\[|[rRbBuU]{0,2}['\"])", r) else ["?"]),
        (r"\bsubprocess\.\w+\s*\(", _a_sh),
        (r"(?<![\w.])(?:os\.)?(?:exec[lv]p?e?|spawn[lv]p?e?)\s*\(|\bpty\.spawn\s*\(", _a_unknown),
        (r"(?<![\w.])(?:fileinput\.)?(?:input|FileInput)\s*\((?=[^)]*inplace\s*=\s*(?:True|1))", _a_arg(0)),
        (r"\.(?:extractall|extract)\s*\(", lambda a, r: [_t(_pos(a)[0])] if _pos(a) else ["./"]),
        (r"(?<![\w.])(?:shutil\.)?unpack_archive\s*\(", lambda a, r: [_t(_pos(a)[1])] if len(_pos(a)) > 1 else ["./"]),
        (r"(?<![\w])(?:\w+\.)*urlretrieve\s*\(", _a_arg(1)),
    ],
    "js": [
        (r"(?<![\w$])(?:writeFile|appendFile|createWriteStream)(?:Sync)?\s*\(", _a_arg(0)),
        (r"(?<![\w$])(?:copyFile)(?:Sync)?\s*\(", _a_arg(1)),
        (_NODE_FS + r"(?:cp|rename|link|symlink)(?:Sync)?\s*\(", _a_arg(1)),
        (_NODE_FS + r"(?:rm|rmdir|unlink|truncate)(?:Sync)?\s*\(", _a_arg(0)),
        (_NODE_FS + r"open(?:Sync)?\s*\(", _a_open(0, 1, "path", "flags")),
        (r"\bBun\.write\s*\(", _a_arg(0)),
        (r"(?<![\w$])(?:exec|execSync|execFile|execFileSync|spawn|spawnSync|fork)\s*\(", _a_sh_js),
        (r"\bBun\.(?:spawn|spawnSync)\s*\(", _a_sh_js),
        (r"\bBun\.\$`", _a_unknown),
    ],
    "rb": [
        (r"\b(?:File|IO)\.(?:write|binwrite)\b", _a_arg(0)),
        (r"\bFile\.(?:open|new)\b", _a_open(0, 1)),
        (r"\bFile\.(?:rename|symlink|link)\b", _a_arg(1)),
        (r"\bFile\.(?:delete|unlink)\b", _a_all),
        (r"\bIO\.copy_stream\b", _a_arg(1)),
        (_RB_FU + r"(?:cp|cp_r|copy|copy_file|copy_entry|mv|move|install|ln|ln_s|ln_sf|link|symlink)\b", _a_last),
        (_RB_FU + r"(?:rm|rm_f|rm_r|rm_rf|remove|remove_file|remove_dir|remove_entry|remove_entry_secure|rmtree|"
                  r"rmdir|touch)\b", _a_all),
        (r"(?<![\w.:])(?:system|exec|spawn)\b", _a_sh_rb),
        (r"\b(?:IO\.popen|Open3\.\w+|Kernel\.(?:system|exec|spawn))\b", _a_sh_rb),
    ],
    "php": [
        (_PHP + r"(?:file_put_contents|unlink|rmdir|touch)\s*\(", _a_arg(0)),
        (_PHP + r"(?:fopen)\s*\(", _a_open(0, 1)),
        (_PHP + r"new\s+SplFileObject\s*\(", _a_open(0, 1)),
        (_PHP + r"(?:copy|rename|symlink|link|move_uploaded_file)\s*\(", _a_arg(1)),
        (_PHP + r"(?:system|exec|shell_exec|passthru|popen|pcntl_exec)\s*\(", _a_sh_php),
        (_PHP + r"proc_open\s*\(", _a_sh_php),
    ],
    "pl": [
        (r"(?<![\w$@%>:])(?:unlink|rmdir)\b", _a_all),
        (r"(?<![\w$@%>:])(?:rename|symlink|link)\b", _a_last),
        (r"(?<![\w$@%>:])(?:copy|move|cp|mv)\b(?=\s*\()", _a_last),
        (r"(?<![\w$@%>:])(?:remove_tree|rmtree)\b", _a_all),
        (r"(?<![\w$@%>:])(?:write_file|write_text|append_file)\b", _a_arg(0)),
        (r"(?<![\w$@%>:])truncate\b", _a_arg(0)),
        (r"(?<![\w$@%>:])(?:sys)?open\b", _a_perl_open),
        (r"(?<![\w$@%>:])(?:system|exec)\b", _a_sh_pl),
        (r"\$\^I", _a_unknown),
    ],
}
_PY_PATH = r"(?:Path|PurePath|PosixPath|WindowsPath)\(\s*(['\"])((?:(?!\1).)*)\1\s*\)\s*$"


def _receiver(code: str, pos: int) -> list[str] | None:  # O(300 * len(code)) | the values of the Path expression ending at pos
    """The longest single atom (a name, Path(...), (a / b)) ending right before the `.method` at pos, composed; a string
    literal is no Path, a receiver that is not understood is None."""
    j = pos  # O(1)
    while j > 0 and code[j - 1] in " \t\r\n":  # O(len(code))
        j -= 1  # O(1)
    for k in range(max(0, j - 300), j):  # O(300)
        c = code[k]  # O(1)
        if not (c == "(" or c.isalpha() or c == "_") or (k > 0 and (code[k - 1].isalnum() or code[k - 1] in "_.")):  # O(1)
            continue  # O(1)
        if _STR_OPEN.match(code, k):  # O(1)
            continue  # O(1)
        r = _compose_raw(code[k:j], _NAMES[0], True)  # O(len(code))
        if r is not None:  # an object this knows nothing about (gzip, a call) keeps the module-function reading  # O(1)
            return None if all(v == _UNK for v in r) else _uniq([_final(v) for v in r])  # O(len(r))
    return None  # O(1)


def _str_name(code: str, pos: int) -> bool:  # O(len(code)) | is the receiver ending at pos a name bound only to str values?
    """`s = 'see X'; s.replace('X', 'Y')` is str.replace, no move: the bare name's every assignment is a single string
    literal, f-string, os.path.join(...) or str(...) term; a for loop, an augmented or any other binding keeps it a Path."""
    rm = re.search(r"(?<![\w.)\]])([A-Za-z_]\w*)\s*$", code[:pos])  # O(len(code))
    if not rm:  # O(1)
        return False  # O(1)
    name = rm.group(1)  # O(1)
    if re.search(r"(?<![\w.])for\s+[\w\s,()]*?\b" + name + r"\b[\w\s,()]*?\s+in\s", code):  # O(len(code))
        return False  # O(1)
    binds = [m for m in _ASSIGN.finditer(code) if m.group(1) == name]  # O(len(code))
    if not binds:  # O(1)
        return False  # O(1)
    for m in binds:  # O(binds)
        rhs = code[m.end():_stmt_end(code, m.end())].strip()  # O(len(code))
        if m.group(2) or not (_STR_OPEN.match(rhs) or re.match(r"(?:os\.path\.join|os\.fspath|str)\s*\(", rhs)):  # O(1)
            return False  # O(1)
        if _compose_raw(rhs, {}, True) is None:  # more than one term: `'a' / p` is a Path  # O(len(rhs))
            return False  # O(1)
    return True  # O(1)


def _py_methods(code: str) -> list[str]:  # O(len(code))
    out: list[str] = []  # O(1)
    for m in re.finditer(r"\.\s*(write_text|write_bytes|touch|unlink|open|rename|replace)\s*\(", code):  # O(len(code))
        name = m.group(1)  # O(1)
        if re.search(r"\b(?:os|shutil)\s*$", code[max(0, m.start() - 12):m.start()]):  # a module function, matched by name  # O(1)
            continue  # O(1)
        if name == "replace" and _str_name(code, m.start()):  # str.replace on a name bound to strings is no move  # O(len(code))
            continue  # O(1)
        lits: list[str | None] = [None]  # O(1)
        recv = _receiver(code, m.start())  # O(300 * len(code))
        if recv is not None:  # a Path, a name or a parenthesised composition: its values, `?` pieces included  # O(1)
            lits = list(recv)  # O(1)
        else:  # O(1)
            pm = re.search(_PY_PATH, code[max(0, m.start() - 400):m.start()])  # O(1)
            lits = [pm.group(2) if pm else None]  # O(1)
        args0, end = _parse_args(code, m.end() - 1, "py", False)  # O(len(code))
        is_os = code[max(0, m.start() - 2):m.start()].endswith("os")  # O(1)
        for lit in lits:  # O(literals)
            for args in _expand(args0):  # O(64)
                out.extend(_py_method(name, lit, args, is_os))  # O(len(args))
    return out  # O(len(out))


def _py_method(name: str, lit: str | None, args: list[Arg], is_os: bool) -> list[str]:  # O(len(args))
    out: list[str] = []  # O(1)
    if True:  # O(1)
        if name in ("rename", "replace"):  # str.replace has no Path receiver: judged only on a literal Path  # O(1)
            if lit is not None:  # O(1)
                out.extend(_a_arg(0)(args, ""))  # O(1)
        elif name == "open":  # O(1)
            if lit is not None:  # Path('p').open('w'): the mode comes first  # O(1)
                p = _pos(args)  # O(len(args))
                mode = p[0] if p else dict(a for a in args if a[0]).get("mode", "")  # O(len(args))
                if mode is None or any(c in mode for c in "wax+"):  # O(len(mode))
                    out.append(lit)  # O(1)
            else:  # io.open('p', 'w'), codecs.open, gzip.open, tarfile.open, x.open('w')  # O(1)
                if is_os:  # os.open  # O(1)
                    pass  # handled by the os.open pattern  # O(1)
                else:  # O(1)
                    p = _pos(args)  # O(len(args))
                    if p and p[0] is not None and re.fullmatch(r"[rwaxbt+U]{1,4}(:\w+)?", p[0]):  # O(len(p[0]))
                        if any(c in p[0] for c in "wax+"):  # O(len(p[0]))
                            out.append("?")  # O(1)
                    else:  # O(1)
                        out.extend(_a_open(0, 1)(args, ""))  # O(len(args))
        else:  # write_text, write_bytes, touch, unlink  # O(1)
            out.append(lit if lit is not None else "?")  # O(1)
    return out  # O(len(out))


def _expand(args: list[Arg]) -> list[list[Arg]]:  # O(64 * len(args)) | a name assigned only literals stands for each
    combos = [args]  # O(1)
    for k, (key, v) in enumerate(args):  # O(len(args))
        if isinstance(v, _Name):  # O(1)
            combos = [c[:k] + [(key, lit)] + c[k + 1:] for c in combos for lit in v.alts][:64]  # O(64)
    return combos  # O(1)


def _code(code: str, lang: str) -> list[str]:  # O(len(code) * |patterns|)
    prev = _NAMES[0]  # O(1)
    _NAMES[0] = _assigned(code, lang)  # O(len(code))
    try:  # O(1)
        return _code1(code, lang)  # O(len(code) * |patterns|)
    finally:  # O(1)
        _NAMES[0] = prev  # O(1)


def _code1(code: str, lang: str) -> list[str]:  # O(len(code) * |patterns|)
    out: list[str] = []  # O(1)
    for pat, action in _CALLS[lang]:  # O(|patterns|)
        for m in re.finditer(pat, code):  # O(len(code))
            at = m.end() - 1 if code[m.end() - 1] == "(" else m.end()  # the opening ( is part of the argument list  # O(1)
            args, end = _parse_args(code, at, lang, lang in ("rb", "pl"))  # O(len(code))
            for c in _expand(args):  # O(64)
                out.extend(action(c, code[at:end]))  # type: ignore[operator]  # O(len(args))
    if lang == "py":  # O(1)
        out.extend(_py_methods(code))  # O(len(code))
    if lang in ("rb", "php", "pl"):  # backticks and qx/%x run shell text  # O(len(code))
        for m in re.finditer(r"`((?:[^`\\]|\\.)*)`|(?:\bqx|%x)\s*([({\[/'\"])", code):  # O(len(code))
            if m.group(1) is not None:  # O(1)
                out.extend(_a_tick(lang)([], m.group(0)))  # O(len(m))
            else:  # qx(...) and %x(...): the text is not read, the target unknown  # O(1)
                out.append("?")  # O(1)
    return _uniq(out)  # O(len(out))


def _eval_code(cmd: str, args: list[str]) -> tuple[str, str] | None:  # O(len(args))
    """The language and the code text of an interpreter's inline-code option, joined when given several times."""
    if _PY.match(cmd):  # O(1)
        lang, skipv, val = "py", {"-W", "-X", "-Q"}, lambda w: (
            re.fullmatch(r"-[BEIOSbdqsuvx]*c", w) is not None)  # O(1)
    elif cmd in _NODE:  # O(1)
        lang, skipv, val = "js", {"-r", "--require", "--import", "--loader", "--experimental-loader", "--input-type",
                                  "-C", "--conditions"}, lambda w: w in ("-e", "-p", "--eval", "--print", "-pe", "-ep")
    elif cmd == "ruby":  # O(1)
        lang, skipv, val = "rb", {"-r", "-I", "-C"}, lambda w: re.fullmatch(r"-[A-Za-z0-9]*e", w) is not None  # O(1)
    elif cmd == "php":  # O(1)
        lang, skipv, val = "php", {"-d", "-c", "-z"}, lambda w: w == "-r"  # O(1)
    elif cmd == "perl":  # -e and -E, also in a cluster (-pe, -lne); -i and -I take the cluster's rest  # O(1)
        lang, skipv, val = "pl", set(), lambda w: re.fullmatch(r"-[A-HJ-Za-hj-z0-9]*[eE]", w) is not None  # O(1)
    else:  # O(1)
        return None  # O(1)
    chunks: list[str] = []  # O(1)
    i = 0  # O(1)
    while i < len(args):  # O(len(args))
        w = args[i]  # O(1)
        if val(w):  # O(1)
            if i + 1 < len(args):  # O(1)
                chunks.append(args[i + 1])  # O(1)
            i += 2  # O(1)
            continue  # O(1)
        if lang == "py" and w.startswith("-c") and len(w) > 2:  # -cCODE  # O(1)
            chunks.append(w[2:])  # O(len(w))
        elif lang == "js" and re.match(r"--(eval|print)=", w):  # O(1)
            chunks.append(w.split("=", 1)[1])  # O(len(w))
        elif w in skipv:  # O(1)
            i += 2  # O(1)
            continue  # O(1)
        elif not w.startswith("-"):  # a script file or module: the rest are its arguments  # O(1)
            break  # O(1)
        i += 1  # O(1)
    return (lang, "\n".join(chunks)) if chunks else None  # O(len(chunks))


# ---------------------------------------------------------------- PowerShell cmdlets

_PS_PATHS = ("path", "literalpath", "filepath", "pspath", "destination", "name", "newname", "outfile")
_PS_SWITCH = frozenset({"force", "recurse", "append", "noclobber", "whatif", "confirm", "passthru", "nonewline",
                        "asbytestream", "container", "usetransaction", "verbose", "debug", "wildcard", "r", "f"})


def _ps(cmd: str, args: list[str]) -> list[str]:  # O(len(args))
    cmdexe = cmd in ("del", "erase", "rd", "copy", "move", "ren")  # cmd.exe style /q /s switches  # O(1)
    cmd = _PS_ALIAS.get(cmd, cmd)  # O(1)
    named: dict[str, list[str]] = {}  # O(1)
    pos: list[str] = []  # O(1)
    i = 0  # O(1)
    while i < len(args):  # O(len(args))
        a = args[i]  # O(1)
        if len(a) > 1 and a[0] == "-" and (a[1].isalpha()):  # a parameter  # O(1)
            name, sep, val = a[1:].partition(":")  # O(len(a))
            low = name.lower()  # O(1)
            cands = [p for p in _PS_PATHS if p.startswith(low)] if len(low) >= 2 else []  # O(1)
            key = low if low in _PS_PATHS else (cands[0] if len(cands) == 1 else low)  # O(1)
            if low == "destinationpath" or (len(low) >= 2 and "destination".startswith(low)):  # O(1)
                key = "destination"  # O(1)
            if sep:  # -Path:a  # O(1)
                named.setdefault(key, []).append(val)  # O(1)
            elif low in _PS_SWITCH:  # O(1)
                pass  # O(1)
            elif i + 1 < len(args):  # O(1)
                named.setdefault(key, []).append(args[i + 1])  # O(1)
                i += 1  # O(1)
        elif not (cmdexe and re.fullmatch(r"/[A-Za-z?](?::\S*)?", a)):  # O(1)
            pos.append(a)  # O(1)
        i += 1  # O(1)

    def split(vals: list[str]) -> list[str]:  # an array argument  # O(sum of len(vals))
        return [("?" if "$" in p else p) for v in vals for p in v.split(",") if p]  # O(sum of len(vals))

    if cmd == "expand-archive":  # the folder the archive is extracted into (default: the current one)  # O(1)
        return _uniq([_dirp(d) for d in split(named.get("destination", [])) or ["."]])  # O(1)
    if cmd == "invoke-webrequest":  # only -OutFile writes  # O(1)
        return _uniq(split(named.get("outfile", [])))  # O(1)
    xfer = cmd in ("copy-item", "move-item")  # O(1)
    srcs = named.get("path", []) + named.get("literalpath", []) + named.get("pspath", [])  # O(1)
    if cmd == "out-file":  # O(1)
        srcs = named.get("filepath", []) + srcs  # O(1)
    if cmd in ("tee-object", "export-csv", "export-clixml"):  # O(1)
        srcs = named.get("filepath", []) + srcs  # O(1)
    if cmd == "remove-item":  # every positional word is a path (cmd.exe's del a b too)  # O(1)
        srcs = srcs + pos  # O(1)
    elif not srcs and pos:  # O(1)
        srcs = [pos[0]]  # O(1)
    if xfer:  # O(1)
        dest = named.get("destination", []) or (pos[1:2] if len(pos) >= 2 and not named.get("path") else
                                                  pos[0:1] if named.get("path") and pos else [])  # O(1)
        return _uniq(split(dest) or ["."])  # O(1)
    paths = split(srcs)  # O(len(srcs))
    if cmd == "rename-item":  # the new name lands in the same folder  # O(1)
        nn = split(named.get("newname", []) or pos[1:2])  # O(1)
        paths = paths + [_join(os.path.dirname(p.replace("\\", "/")), n) if n != "?" and p != "?" else "?"
                         for p in paths for n in nn]  # O(len(paths) * len(nn))
    if cmd == "new-item" and named.get("name"):  # -Path dir -Name f  # O(1)
        nm = split(named["name"])  # O(1)
        paths = [_join(p, n) for p in (paths or ["."]) for n in nm]  # O(len(paths) * len(nm))
    return _uniq(paths)  # O(len(paths))


# ---------------------------------------------------------------- entry point


def targets(words: list[str], cwd: str | None = None, env=None, top: str | None = None,
            text: str | None = None) -> list[str]:  # O(len(words) * |options|)
    """The paths one simple command writes. The optional context only sharpens git: cwd is the directory the shell sits
    in (an operand of `git checkout` counts as a path when it exists there; None: the process's), env the shell
    variables in force for the command (GIT_WORK_TREE; a None value is unknown), top the directory a `!` alias runs in
    (the project root), text the whole command line (a git config or git dir named anywhere makes the config unknown)."""
    return _targets(words, cwd, env, top, text)  # O(len(words) * |options|)


def _targets(words: list[str], cwd: str | None = None, env=None, top: str | None = None,
             text: str | None = None) -> list[str]:  # O(len(words) * |options|)
    if not words:  # O(1)
        return []  # O(1)
    cmd = _cmd(words[0])  # O(len(words[0]))
    args = words[1:]  # O(len(words))
    if cmd == "git":  # O(1)
        return _git(words, cwd, env, top, text)  # O(len(words))
    if cmd in _TARS:  # O(1)
        return _tar(args)  # O(len(args))
    if cmd == "unzip":  # O(1)
        return _unzip(args)  # O(len(args))
    if cmd in _SEVENZ:  # O(1)
        return _sevenz(args)  # O(len(args))
    if cmd == "cpio":  # O(1)
        return _cpio(args)  # O(len(args))
    if cmd in _PS_CMDLETS:  # O(1)
        return _ps(cmd, args)  # O(len(args))
    found = _eval_code(cmd, args)  # O(len(args))
    if found:  # O(1)
        return _code(found[1], found[0])  # O(len(code))
    return []  # O(1)
