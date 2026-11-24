- start f7a89d09442ca1469a1472a364210dd0ed6ade67
- unblocked: dispatched T1 at 13:14:54; waiting on fixes: none
Ruling: docs/fleet.md is edited though open runs B313 and B315 own it in their plans (the brief lists it for no batch); the edits are one sentence each on lines they do not change - lead's ruling - cost if wrong: one rebase conflict at bump
- tests fast passed=3 failed=11 skipped=0 seconds=5.8
- tests fast passed=39 failed=2 skipped=0 seconds=16.6
- tests fast passed=41 failed=0 skipped=0 seconds=11.0
- commit T1 a9209c4a4a remote briefs folder and sl path
- tests fast passed=2 failed=8 skipped=0 seconds=13.5
- tests fast passed=2 failed=8 skipped=0 seconds=13.5
- tests fast passed=71 failed=2 skipped=0 seconds=12.5
- tests fast passed=9 failed=1 skipped=0 seconds=1.4
- tests fast passed=50 failed=1 skipped=0 seconds=11.5
- tests fast passed=36 failed=0 skipped=0 seconds=4.5
- commit T2 af703c6a90 logged-out remote accounts
- tests fast passed=56 failed=0 skipped=0 seconds=8.2
- tests full passed=13974 failed=0 skipped=12 seconds=460.7
Ruling: review-T1,T2 not_run=1 (running-app checks) is ruled out: no app target in this batch - lead's ruling - cost if wrong: none
- tests fast passed=9 failed=1 skipped=0 seconds=2.8
- tests fast passed=13 failed=1 skipped=0 seconds=3.5
- tests fast passed=14 failed=0 skipped=0 seconds=4.5
- commit T1 a37e141f45 remote briefs folder and sl path
- tests full passed=13974 failed=0 skipped=12 seconds=410.3
Ruling: [scope] #1093: the login check before a brief is the start screen (now also `Not logged in`, `Login reached its time limit`) plus the first brief's turn, as a one-turn remote worker makes no API call before it: a first turn whose stop `last` is a sign-in error raises account_signed_out; fleet.py's fallback skips the pair 15 min and spawns local; no probe prompt (lead's ruling).
Ruling: [scope] #1093: fleet wait names the cause for remote workers only: fleet_remote_worker.states reports a busy remote worker whose turn ended on a sign-in stop as blocked and records the pair, so wait prints BLOCKED-UI `(signed out: ...)`; accounts.SIGN_IN_MARKS gains the login-error texts. Local workers' ended branch is fleet_io.py (B313): follow-up (lead's ruling).
