- unblocked: dispatched T1 T2 at 14:09:42; waiting on fixes: none
- start eee19e7c56758074709857049d64862d5f6c8019
- tests fast passed=59 failed=7 skipped=1 seconds=7.2
- tests fast passed=0 failed=1 skipped=0 seconds=1.2
- tests fast passed=66 failed=0 skipped=1 seconds=7.4
- tests fast passed=62 failed=0 skipped=0 seconds=25.8
- commit T1 9d6f729efa collect waits for task stop
- commit T2 4656756fc4 remote brief taken
- tests fast passed=128 failed=0 skipped=1 seconds=17.1
- tests full passed=12600 failed=0 skipped=12 seconds=291.9
- tests fast passed=9 failed=1 skipped=0 seconds=3.5
- tests fast passed=10 failed=0 skipped=0 seconds=3.5
- tests fast passed=9 failed=1 skipped=0 seconds=4.1
- tests fast passed=10 failed=0 skipped=0 seconds=3.8
- commit T2 1051d061c1 remote brief taken
- tests full passed=12601 failed=0 skipped=12 seconds=553.9
Ruling: collect takes only the stop record at or after sent and waits up to 45 s, syncing, for it - the hook's snapshot lags the report by up to 30 s - cost if wrong: one 45 s pause per such worker
Ruling: remote brief resend is unconditional as #909 - a duplicated brief in one turn is harmless - cost if wrong: a one-turn worker reads its brief twice
Ruling: fleet placement local for this build - remote write workers lose work until this ships - cost if wrong: none (local room was enough)
Ruling: FR1 contract items on fleet_remote_collect.sleep dismissed - sleep = time.sleep, builtin signature - cost if wrong: none
