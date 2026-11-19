"""B255 (#967, #969, #970): docs/fleet.md names the lead and restore sign-in checks, the remote resend, the per-account placement skip, the status worktree: line, the lean stop, the gate's refusal and bounds, review-first admission, the account and usage lines, the brief resend and the waits-on suffix."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8").splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"

USAGE = ("- `fleet spawn` names the accounts it left out in one stderr line once it picked one: `accounts skipped: claude2 (<why>), claude3 (signed out)`. "
         "When `claude-profile usage` gives no report at all, the pick takes every account's stored last reading, of any age, and says so on stderr: "
         "`usage: claude-profile usage gave no report; using last readings: claude1 3 h old, ...`, plus `; no stored reading: <accounts>` for listed, signed-in accounts with none, "
         "which count as unknown; a single failed reading also takes its stored reading of any age (#909).")
REFUSAL = ("- A machine-gate refusal names what drove it (#902): `BLOCKED: fleet spawn: machine busy after N s: memory <figures> (N agents, about X GB each)<cause>; "
           "gave up after K checks in N s: <what>; room comes when <ways>; rerun later, or pass --over-limit`. `<figures>` starts with `P% free, floor F%, ` only for a floor refusal, "
           "then `pressure <level>` and the swap and compressor figures it knows; `<cause>` is `; N agents of limit L from <source>`, `; swap free under --min-swap-free-mb M`, "
           "`; N live workers in this run, --max-workers N` or `; a review spawn waits first: <what>`, then `; largest non-agent process <name> X GB` when one holds memory; "
           "`<ways>` names what would make room: `agents end (N running)`, `workers of this run end (N live, --max-workers N)`, `the waiting review spawn (<what>) starts or gives up` "
           "or `<name> (X GB) ends`, else `memory frees up`. The first wait prints `machine busy: <text>; waiting up to S s for <what>` on stderr.")
BOUNDS = ("- `fleet spawn --over-limit --max-workers N --min-swap-free-mb M` (either bound alone works) bounds the override (#902): it still refuses at critical memory pressure, "
          "when swap is set up and its free part (total less used) is under M MB, or when this run has N or more live workers (any state but stopped and blocked); "
          "an admitted bounded override prints `machine limit overridden (--over-limit within --max-workers N and --min-swap-free-mb M): ...` on stderr. "
          "Either flag without `--over-limit` is an error (`--max-workers and --min-swap-free-mb bound --over-limit; pass --over-limit too`); plain `--over-limit` skips every check as before.")
REVIEW = ("- Reviews go first (#902): a package or final reviewer spawn that waits for room writes `machine-wait/<pid>.json` in `~/.superlite` (`SUPERLITE_HOME` moves it), "
          "and any other spawn the gate would admit waits while such a file is live (cause `a review spawn waits first: <what>`), so the review starts first. "
          "The file of a dead process is deleted, and one older than an hour (`WAIT_TTL`) no longer holds other spawns; plain `--over-limit` does not wait for it, a bounded one does.")
WORKTREE = ("- A plain `fleet status` (no `--plan`) in a worktree whose own `.superlite` is not the folder status read, and whose fleet is on where that folder's is off or the reverse, "
            "adds one line after `fleet: on` or `fleet: off`: `worktree: fleet is on in <W>, the folder fleet spawn --plan <W> uses (this status read <S>); sl fleet status --plan <W> shows its workers`, "
            "or `worktree: fleet is off in <W>, the folder fleet spawn --plan <W> checks (this status read <S>); run sl fleet on --plan <W> first` (#904).")
WAITS = ("- A busy local worker's `fleet status` line ends ` waits on <command> <N min>` (` <N> s` under a minute) while a test or build command runs in its pane's process tree: "
         "the worker is alive; keep waiting (#909).")
STOP = ("- `fleet stop` sends `/exit` only to a worker that runs with slash commands, a lead (its launch has no `--disable-slash-commands`), and waits up to 10 s for its agent to end "
        "before it closes the pane; a lean worker gets no `/exit` and no wait, since closing its pane ends it (#930).")
SIGNIN = ("- A lead start and `sl fleet restore` check for the sign-in screen too (#880): a lead start on it marks the account signed out and starts once more on another account "
          "(stderr `Wn account A signed out: Claude Code sign-in screen; retrying on account B`); a second sign-in screen ends in "
          "`BLOCKED: Wn account B signed out: Claude Code sign-in screen; sign in once (CLAUDE_CONFIG_DIR=<dir> claude, then /login), then rerun ...` "
          "(no `CLAUDE_CONFIG_DIR=` for the default folder). Restore relaunches a worker on its own account only, since its `--resume` needs that account's session: "
          "on the sign-in screen it prints `BLOCKED: Wn not restored (account A signed out: Claude Code sign-in screen; sign in once (CLAUDE_CONFIG_DIR=<dir> claude, then /login), then rerun sl fleet restore)`, "
          "and a dead worker keeps its record, so a rerun after the sign-in tries it again.")
BRIEF = ("- A fresh one-turn worker whose pane goes idle with no turn after its first brief gets the brief once more "
         "(stderr `Wn: brief not taken (the pane went idle with no turn); resending once`); a second miss stops the worker and prints "
         "`BLOCKED: Wn <label> not sent (brief not taken after one resend)` (exit 3, #909).")
RESEND = ("- A remote prompt that herdr answers with `timed out waiting for agent status` is sent once more when the agent is idle or done and the first 40 characters "
          "of the prompt's first line are not on its screen; a working agent counts it as sent, and a sign-in screen after the prompt still fails at once with `account_signed_out` (#931).")
PAIR = ("- A remote start or send that fails because an account is signed out on the host skips only that machine and account pair, for 15 minutes (`room-skip.json` `accounts`), "
        "not the whole machine: stderr also prints, once per pair, `placement: account A is signed out on L; L stays in placement with its other accounts; sign A in there once (claude, then /login)`; "
        "the worker starts here and L keeps taking workers on its other accounts. The 10-minute machine skip above stays for every other reason, and a host whose accounts are all skipped "
        "is skipped as `no account with headroom` (#932).")
AFTER = [  # (section, anchor line prefix, the new lines right after it, in order)
    ("## Capacity", "- An account whose `claude-profile usage` reading failed", [USAGE]),
    ("## Capacity", "- Machine gate (#560, #643):", [REFUSAL, BOUNDS, REVIEW]),
    ("## Commands", "- `fleet status` prints `fleet: on` and one line per worker", [WORKTREE, WAITS]),
    ("## Commands", "- `fleet stop W1` or `fleet stop --all` closes workers", [STOP]),
    ("## Troubleshooting", "- Sign-in screen (Claude Code asks to log in):", [SIGNIN]),
    ("## Troubleshooting", "- `agent_prompt_stalled` (a herdr error code", [BRIEF]),
    ("## Remote machines", "- The room answer is cached for 60 s.", [RESEND, PAIR]),
]


def _section(name):
    at = FLEET.index(name)
    end = next((i for i in range(at + 1, len(FLEET)) if FLEET[i].startswith("## ")), len(FLEET))
    return FLEET[at:end]


def test_each_block_follows_its_anchor_in_its_section():
    for section, prefix, block in AFTER:
        lines = _section(section)
        hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
        assert len(hits) == 1, prefix
        assert lines[hits[0] + 1:hits[0] + 1 + len(block)] == block, prefix


def test_each_new_line_appears_once():
    for _, _, block in AFTER:
        for line in block:
            assert FLEET.count(line) == 1, line[:60]


def test_quoted_texts_match_the_code():
    def src(name):
        return (SCRIPTS / name).read_text(encoding="utf-8")
    acc, ml, fleet, io = src("accounts.py"), src("machine_load.py"), src("fleet.py"), src("fleet_io.py")
    assert '"accounts skipped: "' in acc and "using last readings: %s" in acc and "; no stored reading: %s" in acc
    assert "gave up after {k} check" in ml and '"room comes when "' in ml and "memory frees up" in ml
    assert "; largest non-agent process " in ml and "a review spawn waits first: {waiter}" in ml
    assert "machine limit overridden (--over-limit within {_bound_text(bounds)}): " in ml and "WAIT_TTL = 3600" in ml
    assert "machine busy: {text}; waiting up to {int(wait_s)} s for {what}" in ml
    assert "--max-workers and --min-swap-free-mb bound --over-limit; pass --over-limit too" in fleet
    assert '"; rerun later, or pass --over-limit"' in fleet
    assert "worktree: fleet is on in {W}, the folder fleet spawn --plan {W} uses (this status read {S}); sl fleet status --plan {W} shows its workers" in fleet
    assert "worktree: fleet is off in {W}, the folder fleet spawn --plan {W} checks (this status read {S}); run sl fleet on --plan {W} first" in fleet
    assert "not sent ({why})" in fleet and 'SIGNED_OUT_WHY = "signed out: Claude Code sign-in screen"' in fleet
    assert "brief not taken (the pane went idle with no turn); resending once" in io and "brief not taken after one resend" in io
    assert 'f" waits on {lab} "' in src("fleet_waits.py")
    assert 'wait_state(name, ["unknown"], 10000)' in src("herdr_client.py")
    lead = src("fleet_lead.py")
    assert "; retrying on account {account}" in lead and "; sign in once ({var}claude, then /login), then rerun" in lead
    restore = src("fleet_restore.py")
    assert "not restored (account {account} signed out: Claude Code sign-in screen; sign in once ({var}claude, then /login), then rerun {SL_CMD})" in restore
    assert 'SL_CMD = "sl fleet restore"' in restore
    assert 'STATUS_MSG = "timed out waiting for agent status"' in src("fleet_remote_worker.py")
    place = src("fleet_placement.py")
    assert "PAIR_MINUTES = 15.0" in place and "stays in placement with its other accounts; " in place
    assert "sign {name} in there once (claude, then /login)" in place
