- start a021bb1eafa815752b2330d7d0151efaa0df9485
- unblocked: dispatched T1 at 08:35:44; waiting on fixes: none
- commit T1 95e2a6afc0 sealed lead gh seal settings
- tests fast passed=96 failed=0 skipped=0 seconds=4.6
- tests full passed=13568 failed=0 skipped=12 seconds=352.8
Ruling: [scope] lead only; sealed workers are a follow-up (fleet.py) - #1041 names the lead and the batch's files - cost if wrong: workers of a sealed lead keep the profile hole
Ruling: --settings env file, not a shell unset line - only a settings value also beats a user-settings env - cost if wrong: a managed env token still wins
