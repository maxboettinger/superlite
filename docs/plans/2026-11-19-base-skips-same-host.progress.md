- unblocked: dispatched T1 at 20:03:59; waiting on fixes: none
- start bd8fd1e6054cd4c55beeb355a5e1c17ed4fcc9fe
Ruling: fleet placement local - W2 on maxbook became unreachable (ssh timeout) mid-T1; redispatched T1 on this Mac - cost if wrong: one local worker slot
- tests fast passed=0 failed=9 skipped=0 seconds=3.3
- tests fast passed=9 failed=0 skipped=0 seconds=2.8
- tests fast passed=32 failed=0 skipped=0 seconds=11.2
- commit T1 87f12ad6f5 base on the full run's host
- tests fast passed=9 failed=0 skipped=0 seconds=1.5
- tests fast passed=32 failed=0 skipped=0 seconds=4.7
- tests full passed=13148 failed=0 skipped=12 seconds=618.7
Ruling: [scope] #999's host half is fixed (live: base bd8fd1e skips 11 of 12, B263 saw 8); test_guard_parity::test_parity_existing_suites skips only when the session collects every parity file, which a base run narrowed to the skipped files never does - follow-up, not this batch - cost if wrong: one more batch
- tests fast passed=8 failed=2 skipped=0 seconds=1.6
- tests fast passed=10 failed=0 skipped=0 seconds=1.5
- tests fast passed=10 failed=0 skipped=0 seconds=1.4
- commit T1 9cd9481161 base on the full run's host
Ruling: no second final review round - FR1's two tier-1 findings were fixed with regression tests (10 passed) in the same requoting code; the full suite reruns - cost if wrong: a requoting defect ships to a rarely used path
- tests full passed=13149 failed=0 skipped=12 seconds=318.6
