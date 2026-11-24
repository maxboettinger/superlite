# #1085 which packet sections and `run_tests --wait` lines grew

Scan time 2026-11-24T14:20Z, one run per script on this Mac's transcripts (`~/.claude/projects` and each `~/.claude-account*/projects`, files with mtime from 2026-10-05). Windows (UTC, by line timestamp) as in #1059: before = 2026-10-05T00:00:00Z to 2026-11-15T19:37:20Z (#918 merged); after = 2026-11-16T00:00:00Z to the scan time. Aggregate numbers only; a heading that names a project file is counted as `<file sections>`.

Unit: one tool result that reads `review-packet.md` (over 500 chars; Read line-number prefixes stripped), split at its `#` heading lines; one Bash result holding `run_tests` and `--wait`. "mean" is chars per packet read or per wait call, counting 0 where the part is absent, so the mean deltas add up; "share" is the fraction of reads or calls holding the part; "p50" is the median where present.

## Packet sections (n before 1766, after 1058 packet reads)

| section | mean before | mean after | delta | share before -> after | p50 present before -> after |
|---|---|---|---|---|---|
| whole read (Read prefixes stripped) | 24844 | 26909 | +2065 | 1.00 -> 1.00 | 24292 -> 28211 |
| `## Global constraints` (fleet `with_constraints`, kept by #1059) | 213 | 1448 | +1235 | 0.08 -> 0.41 | 2516 -> 3102 |
| `## 6. Diff stat` | 730 | 1392 | +663 | 0.52 -> 0.45 | 894 -> 1622 |
| `<file sections>` (inlined files under path headings) | 18718 | 19086 | +369 | 0.68 -> 0.76 | 26852 -> 25686 |
| `## Standing note` | 13 | 347 | +334 | 0.01 -> 0.23 | 1882 -> 1531 |
| `## 0c. Coverage` | 262 | 483 | +221 | 0.18 -> 0.25 | 1305 -> 1758 |
| head, `REVIEW REQUIRED` | 136 | 343 | +207 | 0.16 -> 0.14 | 403 -> 1544 |
| head, `REVIEW REQUIRED (code diffs cut)` (#819) | 0 | 167 | +167 | 0.00 -> 0.09 | 0 -> 1282 |
| `## Render evidence` | 44 | 191 | +147 | 0.02 -> 0.08 | 1394 -> 1653 |
| head, `REVIEW REQUIRED (tool checks only)` | 86 | 159 | +73 | 0.09 -> 0.09 | 846 -> 1425 |

### Head lines (n before 964, after 491 packets with a `# Review packet` first line)

| head line | mean before | mean after | delta | share before -> after | p50 present before -> after |
|---|---|---|---|---|---|
| `Cut to fit the size cap: ...` | 121 | 540 | +420 | 0.24 -> 0.66 | 184 -> 291 |
| `Read in full before your verdict ...` (#819) | 0 | 219 | +219 | 0.00 -> 0.39 | 0 -> 210 |
| `Answer in one turn: ...` (replaced `Answer in one turn, no tools ...`, -102) | 108 | 317 | +209 | 0.34 -> 0.99 | 320 -> 320 |
| `This packet has N lines ...` | 71 | 210 | +139 | 0.34 -> 0.99 | 211 -> 211 |
| `Tests shard: ...` | 93 | 151 | +58 | 0.40 -> 0.65 | 233 -> 232 |

### Cut line parts (same packets)

| part | mean before | mean after | delta | share before -> after |
|---|---|---|---|---|
| whole Cut line | 120 | 539 | +418 | 0.24 -> 0.66 |
| `section 8 truncated: F` entries (p50 4 entries per line after) | 59 | 354 | +295 | 0.23 -> 0.65 |
| of those, entries whose file the `Read in full` line names again | 0 | 188 | +188 | 0.00 -> 0.38 |
| `section 8 left out: ...` entry | 37 | 143 | +106 | 0.04 -> 0.22 |
| of those, names the `Read in full` line names again | 0 | 54 | +54 | 0.00 -> 0.04 |

### Diff stat shape (packets with a `## 6. Diff stat` block, n before 886, after 473)

| part | mean before | mean after | p50 before -> after |
|---|---|---|---|
| whole block | 1367 | 3079 | 888 -> 1625 |
| rows | 16 | 35 | 11 -> 21 |
| alignment padding before ` \| ` | 301 | 801 | 160 -> 342 |
| `+`/`-` bar characters | 166 | 311 | 136 -> 217 |

The stat code is unchanged since 2026-11-03 (#109): the block grew with the number of changed files; padding and bars are 36% of it after.

## `run_tests --wait` output (n before 11662, after 7033 calls)

| line or part | mean before | mean after | delta | share before -> after | p50 present before -> after |
|---|---|---|---|---|---|
| whole result | 643 | 725 | +82 | 1.00 -> 1.00 | 393 -> 603 |
| last line `tests (MODE): ...` | 39 | 173 | +134 | 0.62 -> 0.83 | 33 -> 164 |
| JSON `"summary": "<abs path>"` (#918) | 0 | 76 | +76 | 0.00 -> 0.49 | 0 -> 155 |
| stderr `output: <abs path>` | 68 | 117 | +49 | 0.43 -> 0.75 | 155 -> 155 |
| other JSON lines | 167 | 83 | -84 | 0.25 -> 0.19 | 213 -> 251 |

Last line parts (n before 8166, after 6617 `tests (MODE):` lines):

| part | mean before | mean after | delta | share before -> after | p50 present before -> after |
|---|---|---|---|---|---|
| `; failing: <name>: <reason>` (#912 in #918: each failure's reason) | 18 | 106 | +88 | 0.16 -> 0.45 | 71 -> 176 |
| `; lacks N changed files of the run root: ...` (#818 in 03162b7a) | 0 | 38 | +38 | 0.00 -> 0.20 | 0 -> 217 |
| `; tree <tree>` (#818) | 0 | 8 | +8 | 0.00 -> 0.27 | 0 -> 26 |
| `; result bundle <path>` (#818) | 0 | 1 | +1 | 0.00 -> 0.01 | 0 -> 175 |

## What B317 trims and keeps

- Trimmed: the `--wait` stdout JSON leaves out `output`, `warning`, `tree`, `lacks`, `drift` and `result_bundles`, which its stderr lines print (`output:`, `warning:`, the last line's tested tail); the summary file the JSON's `summary` key names keeps them.
- Trimmed: diff stat rows lose the alignment padding and the `+`/`-` bar (` path | +A -D`), about 1.1k chars per packet at the after-window mean.
- Trimmed: the head's Cut line merges its `section 8 truncated:` entries into one and leaves out the files the `Read in full` line names (about 190 to 240 chars per packet at the after-window mean); `section 8 left out:` stays whole, since the final reviewer may read only files that entry names.
- Kept: the failure reasons on the last line (#912; red results followed by a log read fell from 33.7% to 23.1%, #1059), the JSON `summary` key (#918), the Global constraints in review briefs (main's ruling in #1059), the standing note, Coverage and Render evidence (content of the batch, capped where a cap exists), the head's instruction lines.

## Scan scripts

Section and line-kind split (`sections2.py`):

```python
#!/usr/bin/env python3
"""#1085: per-section packet chars and per-line-kind run_tests --wait chars, before vs after #918. Aggregates only."""
import glob, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timezone
HOME = os.path.expanduser("~")
ROOTS = [f"{HOME}/.claude/projects"] + sorted(glob.glob(f"{HOME}/.claude-account*/projects"))
MIN_MTIME = datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()
W_BEFORE = ("2026-10-05T00:00:00Z", "2026-11-15T19:37:20Z")
W_AFTER = "2026-11-16T00:00:00Z"
PACKET_RE = re.compile(r"review-packet\.md")
READ_CMD = re.compile(r"\b(cat|sed|head)\b")
LNUM = re.compile(r"^\s*\d+(\t|→)", re.M)
def window(ts):
    if not isinstance(ts, str): return None
    t = re.sub(r"\.\d+Z$", "Z", ts)
    if W_BEFORE[0] <= t <= W_BEFORE[1]: return "before"
    if t >= W_AFTER: return "after"
    return None
def text_of(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""
def norm(s, n=40):
    s = re.sub(r"\d+", "N", s.strip())
    s = re.sub(r"`[^`]*`", "`x`", s)
    return s[:n]
def linekey(l):
    l = l.strip()
    if not l: return "<blank>"
    m = re.match(r"([A-Za-z_ ()/.\-]{1,40}?)[:=]", l)
    return norm(m.group(1)) + ":" if m else "~" + norm(l, 25)
pk = {"before": [], "after": []}  # list of dict section->chars
wt = {"before": [], "after": []}  # list of dict linekey->chars
for root in ROOTS:
    for path in glob.glob(f"{root}/**/*.jsonl", recursive=True):
        try:
            if os.path.getmtime(path) < MIN_MTIME: continue
        except OSError: continue
        calls = {}
        with open(path, errors="replace") as f:
            for line in f:
                if "tool_" not in line: continue
                try: d = json.loads(line)
                except ValueError: continue
                if not isinstance(d, dict) or not isinstance(d.get("message"), dict): continue
                w = window(d.get("timestamp"))
                content = d["message"].get("content")
                if not isinstance(content, list): continue
                for b in content:
                    if not isinstance(b, dict): continue
                    if b.get("type") == "tool_use":
                        calls[b.get("id")] = (b.get("name"), b.get("input") or {})
                    elif b.get("type") == "tool_result" and w:
                        name, inp = calls.get(b.get("tool_use_id"), (None, {}))
                        if name is None: continue
                        tx = text_of(b.get("content"))
                        cmd = inp.get("command", "") if name == "Bash" else ""
                        tgt = cmd if name == "Bash" else inp.get("file_path", "")
                        rd = name == "Read" or (name == "Bash" and READ_CMD.search(cmd))
                        if rd and PACKET_RE.search(tgt) and len(tx) > 500:
                            body = LNUM.sub("", tx) if name == "Read" else tx
                            sec = defaultdict(int); cur = "<top>"
                            for l in body.splitlines(True):
                                if l.startswith("#"):
                                    h = l.lstrip("# ").strip()
                                    cur = "<FILE>" if ("/" in h.split(" ")[0] or re.search(r"\.\w{1,6}$", h.split(" ")[0])) else norm(h, 50)
                                sec[cur] += len(l)
                            sec["<TOTAL>"] = len(body); sec["<RAW>"] = len(tx)
                            pk[w].append(dict(sec))
                        if name == "Bash" and "run_tests" in cmd and "--wait" in cmd:
                            k = defaultdict(int)
                            for l in tx.splitlines(True):
                                lk = linekey(l)
                                if lk.startswith("~\"") and not lk.startswith("~\"summary") and ":" not in lk: lk = "<json-other>"
                                k[lk] += len(l)
                            k["<TOTAL>"] = len(tx); k["<LINES>"] = tx.count("\n") + 1
                            wt[w].append(dict(k))
def report(name, data, top=30):
    print(f"## {name}: n before {len(data['before'])}, after {len(data['after'])}")
    keys = set().union(*[set(x) for w in data for x in data[w]])
    rows = []
    for k in keys:
        r = {}
        for w in ("before", "after"):
            vals = [x.get(k, 0) for x in data[w]]; n = len(vals) or 1
            have = sorted(v for v in vals if v)
            r[w] = (sum(vals) / n, len(have) / n, have[len(have) // 2] if have else 0)
        rows.append((r["after"][0] - r["before"][0], k, r))
    rows.sort(key=lambda x: -abs(x[0]))
    print("| key | mean/before | mean/after | delta | share b->a | p50-when-present b->a |")
    for dlt, k, r in rows[:top]:
        print(f"| {k} | {r['before'][0]:.0f} | {r['after'][0]:.0f} | {dlt:+.0f} | {r['before'][1]:.2f}->{r['after'][1]:.2f} | {r['before'][2]}->{r['after'][2]} |")
json.dump({"pk": pk, "wt": wt}, open("dump.json", "w"))
report("packet sections (mean chars per packet read)", pk, 40)
report("run_tests --wait line kinds (mean chars per call)", wt, 40)
```

Head lines, diff stat shape, last-line parts (`detail.py`):

```python
#!/usr/bin/env python3
"""#1085 detail: packet head line kinds, diff stat line shape, wait summary-line tail parts. Aggregates only."""
import glob, json, os, re
from collections import defaultdict
from datetime import datetime, timezone
HOME = os.path.expanduser("~")
ROOTS = [f"{HOME}/.claude/projects"] + sorted(glob.glob(f"{HOME}/.claude-account*/projects"))
MIN_MTIME = datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()
LNUM = re.compile(r"^\s*\d+(\t|→)", re.M)
def window(ts):
    if not isinstance(ts, str): return None
    t = re.sub(r"\.\d+Z$", "Z", ts)
    if "2026-10-05T00:00:00Z" <= t <= "2026-11-15T19:37:20Z": return "before"
    if t >= "2026-11-16T00:00:00Z": return "after"
def text_of(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""
def key(l, n=28):
    l = re.sub(r"\d+", "N", l.strip())
    m = re.match(r"([^:]{1,40}?):", l)
    return (m.group(1) if m else l)[:n]
head = {"before": [], "after": []}; stat = {"before": [], "after": []}; tail = {"before": [], "after": []}
for root in ROOTS:
    for path in glob.glob(f"{root}/**/*.jsonl", recursive=True):
        try:
            if os.path.getmtime(path) < MIN_MTIME: continue
        except OSError: continue
        calls = {}
        with open(path, errors="replace") as f:
            for line in f:
                if "tool_" not in line: continue
                try: d = json.loads(line)
                except ValueError: continue
                if not isinstance(d, dict) or not isinstance(d.get("message"), dict): continue
                w = window(d.get("timestamp")); c = d["message"].get("content")
                if not isinstance(c, list): continue
                for b in c:
                    if not isinstance(b, dict): continue
                    if b.get("type") == "tool_use": calls[b.get("id")] = (b.get("name"), b.get("input") or {})
                    elif b.get("type") == "tool_result" and w:
                        name, inp = calls.get(b.get("tool_use_id"), (None, {}))
                        if name is None: continue
                        tx = text_of(b.get("content")); cmd = inp.get("command", "") if name == "Bash" else ""
                        tgt = cmd if name == "Bash" else inp.get("file_path", "")
                        rd = name == "Read" or (name == "Bash" and re.search(r"\b(cat|sed|head)\b", cmd))
                        if rd and "review-packet.md" in tgt and len(tx) > 500:
                            body = LNUM.sub("", tx) if name == "Read" else tx
                            ls = body.splitlines()
                            if not ls or not ls[0].startswith("# Review packet"): continue
                            h = defaultdict(int)
                            for l in ls[1:]:
                                if l.startswith("## "): break
                                h[key(l)] += len(l) + 1
                            head[w].append(dict(h))
                            m = re.search(r"^## 6\. Diff stat\n```\n(.*?)\n```", body, re.S | re.M)
                            if m:
                                sl = m.group(1).splitlines()
                                bars = sum(len(re.search(r"[+\-]*$", x).group(0)) for x in sl if "|" in x)
                                stat[w].append({"lines": len(sl), "chars": len(m.group(1)), "bars": bars,
                                                "pad": sum(len(re.search(r" *\|", x).group(0)) - 1 for x in sl if "|" in x)})
                        if name == "Bash" and "run_tests" in cmd and "--wait" in cmd:
                            for l in tx.splitlines():
                                if re.match(r"tests \([^)]*\):", l):
                                    parts = defaultdict(int)
                                    segs = l.split("; ")
                                    parts["<head>"] += len(segs[0])
                                    for s in segs[1:]:
                                        parts[re.sub(r"\d+", "N", s.split(" ")[0] + (" " + s.split(" ")[1] if s.startswith("result") and len(s.split(" ")) > 1 else ""))] += len(s) + 2
                                    parts["<LINE>"] = len(l)
                                    tail[w].append(dict(parts))
def rep(name, data, top=25):
    print(f"## {name}: n before {len(data['before'])}, after {len(data['after'])}")
    keys = set().union(*[set(x) for w in data for x in data[w]]); rows = []
    for k in keys:
        r = {}
        for w in ("before", "after"):
            vals = [x.get(k, 0) for x in data[w]]; n = len(vals) or 1
            have = sorted(v for v in vals if v)
            r[w] = (sum(vals) / n, len(have) / n, have[len(have) // 2] if have else 0)
        rows.append((r["after"][0] - r["before"][0], k, r))
    rows.sort(key=lambda x: -abs(x[0]))
    for dlt, k, r in rows[:top]:
        print(f"| {k} | {r['before'][0]:.0f} | {r['after'][0]:.0f} | {dlt:+.0f} | {r['before'][1]:.2f}->{r['after'][1]:.2f} | {r['before'][2]}->{r['after'][2]} |")
rep("packet head line kinds (mean chars per packet)", head)
rep("diff stat shape (mean per packet)", stat)
rep("wait 'tests (MODE):' line parts (mean chars per line)", tail)
```

Cut line parts (`cutline.py`):

```python
#!/usr/bin/env python3
"""#1085 detail: packet head line kinds, diff stat line shape, wait summary-line tail parts. Aggregates only."""
import glob, json, os, re
from collections import defaultdict
from datetime import datetime, timezone
HOME = os.path.expanduser("~")
ROOTS = [f"{HOME}/.claude/projects"] + sorted(glob.glob(f"{HOME}/.claude-account*/projects"))
MIN_MTIME = datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()
LNUM = re.compile(r"^\s*\d+(\t|→)", re.M)
def window(ts):
    if not isinstance(ts, str): return None
    t = re.sub(r"\.\d+Z$", "Z", ts)
    if "2026-10-05T00:00:00Z" <= t <= "2026-11-15T19:37:20Z": return "before"
    if t >= "2026-11-16T00:00:00Z": return "after"
def text_of(c):
    if isinstance(c, str): return c
    if isinstance(c, list): return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""
def key(l, n=28):
    l = re.sub(r"\d+", "N", l.strip())
    m = re.match(r"([^:]{1,40}?):", l)
    return (m.group(1) if m else l)[:n]
cutk = {"before": [], "after": []}
for root in ROOTS:
    for path in glob.glob(f"{root}/**/*.jsonl", recursive=True):
        try:
            if os.path.getmtime(path) < MIN_MTIME: continue
        except OSError: continue
        calls = {}
        with open(path, errors="replace") as f:
            for line in f:
                if "tool_" not in line: continue
                try: d = json.loads(line)
                except ValueError: continue
                if not isinstance(d, dict) or not isinstance(d.get("message"), dict): continue
                w = window(d.get("timestamp")); c = d["message"].get("content")
                if not isinstance(c, list): continue
                for b in c:
                    if not isinstance(b, dict): continue
                    if b.get("type") == "tool_use": calls[b.get("id")] = (b.get("name"), b.get("input") or {})
                    elif b.get("type") == "tool_result" and w:
                        name, inp = calls.get(b.get("tool_use_id"), (None, {}))
                        if name is None: continue
                        tx = text_of(b.get("content")); cmd = inp.get("command", "") if name == "Bash" else ""
                        tgt = cmd if name == "Bash" else inp.get("file_path", "")
                        rd = name == "Read" or (name == "Bash" and re.search(r"\b(cat|sed|head)\b", cmd))
                        if rd and "review-packet.md" in tgt and len(tx) > 500:
                            body = LNUM.sub("", tx) if name == "Read" else tx
                            ls = body.splitlines()
                            if not ls or not ls[0].startswith("# Review packet"): continue
                            k = defaultdict(int)
                            cut = next((l for l in ls[:30] if l.startswith("Cut to fit the size cap: ")), None)
                            rif = next((l for l in ls[:30] if l.startswith("Read in full before your verdict")), "")
                            must = set(x.strip() for x in rif.split("): ", 1)[-1].split(",")) if rif else set()
                            if cut:
                                k["<cutline>"] = len(cut)
                                for e in cut[len("Cut to fit the size cap: "):].split("; "):
                                    kind = re.sub(r"\d+", "N", e.split(":")[0])[:30]
                                    k[kind] += len(e) + 2
                                    if e.startswith("section 8 truncated: ") and e[len("section 8 truncated: "):].strip() in must:
                                        k["dup: truncated entry also on Read-in-full"] += len(e) + 2
                                    if e.startswith("section 8 left out: "):
                                        names = [x.strip() for x in e[len("section 8 left out: "):].split(",")]
                                        k["dup: left-out names also on Read-in-full"] += sum(len(x) + 2 for x in names if x in must)
                                k["n truncated entries"] = sum(1 for e in cut.split("; ") if "section 8 truncated: " in e)
                            if rif: k["<read-in-full>"] = len(rif)
                            cutk[w].append(dict(k))
def rep(name, data, top=25):
    print(f"## {name}: n before {len(data['before'])}, after {len(data['after'])}")
    keys = set().union(*[set(x) for w in data for x in data[w]]); rows = []
    for k in keys:
        r = {}
        for w in ("before", "after"):
            vals = [x.get(k, 0) for x in data[w]]; n = len(vals) or 1
            have = sorted(v for v in vals if v)
            r[w] = (sum(vals) / n, len(have) / n, have[len(have) // 2] if have else 0)
        rows.append((r["after"][0] - r["before"][0], k, r))
    rows.sort(key=lambda x: -abs(x[0]))
    for dlt, k, r in rows[:top]:
        print(f"| {k} | {r['before'][0]:.0f} | {r['after'][0]:.0f} | {dlt:+.0f} | {r['before'][1]:.2f}->{r['after'][1]:.2f} | {r['before'][2]}->{r['after'][2]} |")
rep("cut line parts (mean chars per packet)", cutk)

```
