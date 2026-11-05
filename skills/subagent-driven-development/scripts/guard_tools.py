"""Tools and interpreters: name the paths a simple command writes.

targets(words) takes the already-decoded words of one simple command (the lexer did the quoting) and returns the
paths it writes, as written: "." for a whole-tree discard (git reset --hard), "?" for a write whose target is not
literal, a directory with a trailing "/" for an extraction into it. COMMANDS holds the lower-case command names this
module reads (a path and ".exe" are stripped from the command word first).
"""

import os
import re

_PY = re.compile(r"^(python|pypy|py)[\d.]*$")  # O(1)
_NODE = frozenset({"node", "nodejs", "bun"})
_SEVENZ = frozenset({"7z", "7za", "7zr", "7zz"})
_PS_CMDLETS = frozenset({
    "set-content", "add-content", "clear-content", "out-file", "new-item", "remove-item", "copy-item", "move-item",
    "rename-item",
})
COMMANDS: frozenset[str] = frozenset(
    {"git", "tar", "unzip", "cpio", "ruby", "php", "python", "python3", "python2", "py", "pypy", "pypy3"}
    | _NODE | _SEVENZ | _PS_CMDLETS
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


def _git(words: list[str]) -> list[str]:  # O(len(words))
    base, sub, i, cflag, wt, cfg = "", "", 1, False, None, {}  # O(1)
    n = len(words)  # O(1)
    while i < n:  # O(len(words))
        a = words[i]  # O(1)
        if a in _GIT_VALOPTS:  # O(1)
            v = words[i + 1] if i + 1 < n else ""  # O(1)
            if a == "-C":  # O(1)
                base = _join(base, v) if base else v  # O(len(v))
            elif a == "--work-tree":  # O(1)
                wt = v  # O(1)
            elif a == "-c":  # O(1)
                k, _, val = v.partition("=")  # O(len(v))
                cfg[k.lower()] = val  # O(1)
            i += 2  # O(1)
            continue  # O(1)
        if a.startswith("--work-tree="):  # O(1)
            wt = a.split("=", 1)[1]  # O(len(a))
        elif a.startswith("-C") and len(a) > 2:  # O(1)
            base = _join(base, a[2:]) if base else a[2:]  # O(len(a))
        elif a.startswith("-"):  # O(1)
            pass  # O(1)
        else:  # O(1)
            sub = a  # O(1)
            i += 1  # O(1)
            break  # O(1)
        i += 1  # O(1)
    if not sub:  # O(1)
        return []  # O(1)
    cflag = False  # O(1)
    if wt is None and "core.worktree" in cfg:  # O(1)
        wt = cfg["core.worktree"]  # O(1)
    if wt is not None:  # O(1)
        base = wt if wt.startswith("/") or not base else _join(base, wt)  # O(len(wt))
    if sub not in _GIT_CMDS:  # O(1)
        if any(k.startswith("alias.") and k[6:] == sub.lower() for k in cfg):  # O(len(cfg))
            return ["?"]  # an alias from -c: its body is not read here  # O(1)
        return []  # O(1)
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

    if sub in ("apply", "am"):  # O(1)
        return ["?"]  # O(1)
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
        return whole() if _git_flag(args, "f", "force", sub) or _git_flag(args, "a", "all", sub) else []  # O(len(args))
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
        paths = ops + paths or ["."]  # O(len(ops))
    else:  # checkout: without --, <tree-ish> <path>..., or one operand that names an existing path  # O(1)
        if _git_flag(args, "f", "force", sub):  # O(len(args))
            return whole()  # O(1)
        if not dd:  # O(1)
            if len(ops) >= 2:  # O(1)
                paths = ops[1:]  # O(len(ops))
            if ops and os.path.exists(_join(base, ops[0])):  # O(1)
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
        (r"(?<![\w])(?:\w+\.)*(?:copyfile|copy2|copytree|rmtree)\s*\(", _a_arg(1)),
        (_PYP + r"(?:remove|removedirs|unlink|rmdir|rmtree|truncate)\s*\(", _a_arg(0)),
    ],
    "js": [
        (r"(?<![\w$])(?:writeFile|appendFile|createWriteStream)(?:Sync)?\s*\(", _a_arg(0)),
        (r"(?<![\w$])(?:copyFile)(?:Sync)?\s*\(", _a_arg(1)),
        (_NODE_FS + r"(?:cp|rename|link|symlink)(?:Sync)?\s*\(", _a_arg(1)),
        (_NODE_FS + r"(?:rm|rmdir|unlink|truncate)(?:Sync)?\s*\(", _a_arg(0)),
        (_NODE_FS + r"open(?:Sync)?\s*\(", _a_open(0, 1, "path", "flags")),
        (r"\bBun\.write\s*\(", _a_arg(0)),
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
    ],
    "php": [
        (_PHP + r"(?:file_put_contents|unlink|rmdir|touch)\s*\(", _a_arg(0)),
        (_PHP + r"(?:fopen)\s*\(", _a_open(0, 1)),
        (_PHP + r"new\s+SplFileObject\s*\(", _a_open(0, 1)),
        (_PHP + r"(?:copy|rename|symlink|link|move_uploaded_file)\s*\(", _a_arg(1)),
    ],
}
_PY_PATH = r"(?:Path|PurePath|PosixPath|WindowsPath)\(\s*(['\"])((?:(?!\1).)*)\1\s*\)\s*$"


def _py_methods(code: str) -> list[str]:  # O(len(code))
    out: list[str] = []  # O(1)
    for m in re.finditer(r"\.\s*(write_text|write_bytes|touch|unlink|open|rename|replace)\s*\(", code):  # O(len(code))
        name = m.group(1)  # O(1)
        if re.search(r"\b(?:os|shutil)\s*$", code[max(0, m.start() - 12):m.start()]):  # a module function, matched by name  # O(1)
            continue  # O(1)
        pm = re.search(_PY_PATH, code[max(0, m.start() - 400):m.start()])  # O(1)
        lit = pm.group(2) if pm else None  # O(1)
        args, end = _parse_args(code, m.end() - 1, "py", False)  # O(len(code))
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
                if code[max(0, m.start() - 2):m.start()].endswith("os"):  # os.open  # O(1)
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


def _code(code: str, lang: str) -> list[str]:  # O(len(code) * |patterns|)
    out: list[str] = []  # O(1)
    for pat, action in _CALLS[lang]:  # O(|patterns|)
        for m in re.finditer(pat, code):  # O(len(code))
            at = m.end() - 1 if code[m.end() - 1] == "(" else m.end()  # the opening ( is part of the argument list  # O(1)
            args, end = _parse_args(code, at, lang, lang == "rb")  # O(len(code))
            out.extend(action(args, code[at:end]))  # type: ignore[operator]  # O(len(args))
    if lang == "py":  # O(1)
        out.extend(_py_methods(code))  # O(len(code))
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

_PS_PATHS = ("path", "literalpath", "filepath", "pspath", "destination", "name")
_PS_SWITCH = frozenset({"force", "recurse", "append", "noclobber", "whatif", "confirm", "passthru", "nonewline",
                        "asbytestream", "container", "usetransaction", "verbose", "debug", "wildcard", "r", "f"})


def _ps(cmd: str, args: list[str]) -> list[str]:  # O(len(args))
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
            if sep:  # -Path:a  # O(1)
                named.setdefault(key, []).append(val)  # O(1)
            elif low in _PS_SWITCH:  # O(1)
                pass  # O(1)
            elif i + 1 < len(args):  # O(1)
                named.setdefault(key, []).append(args[i + 1])  # O(1)
                i += 1  # O(1)
        else:  # O(1)
            pos.append(a)  # O(1)
        i += 1  # O(1)

    def split(vals: list[str]) -> list[str]:  # an array argument  # O(sum of len(vals))
        return [("?" if "$" in p else p) for v in vals for p in v.split(",") if p]  # O(sum of len(vals))

    xfer = cmd in ("copy-item", "move-item")  # O(1)
    srcs = named.get("path", []) + named.get("literalpath", []) + named.get("pspath", [])  # O(1)
    if cmd == "out-file":  # O(1)
        srcs = named.get("filepath", []) + srcs  # O(1)
    if not srcs and pos:  # O(1)
        srcs = [pos[0]]  # O(1)
    if xfer:  # O(1)
        dest = named.get("destination", []) or (pos[1:2] if len(pos) >= 2 and not named.get("path") else
                                                  pos[0:1] if named.get("path") and pos else [])  # O(1)
        return _uniq(split(dest) or ["."])  # O(1)
    paths = split(srcs)  # O(len(srcs))
    if cmd == "new-item" and named.get("name"):  # -Path dir -Name f  # O(1)
        nm = split(named["name"])  # O(1)
        paths = [_join(p, n) for p in (paths or ["."]) for n in nm]  # O(len(paths) * len(nm))
    return _uniq(paths)  # O(len(paths))


# ---------------------------------------------------------------- entry point


def targets(words: list[str]) -> list[str]:  # O(len(words) * |options|)
    if not words:  # O(1)
        return []  # O(1)
    cmd = _cmd(words[0])  # O(len(words[0]))
    args = words[1:]  # O(len(words))
    if cmd == "git":  # O(1)
        return _git(words)  # O(len(words))
    if cmd == "tar":  # O(1)
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
