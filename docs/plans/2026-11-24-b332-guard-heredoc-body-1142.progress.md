- start f424822185cc1b7a5b6b34650ea2fd97f4fcd37b
- unblocked: dispatched T1 at 17:45:43; waiting on fixes: none
- tests fast passed=22 failed=12 skipped=0 seconds=1.0
- tests fast passed=240 failed=0 skipped=0 seconds=11.9
Ruling: a file the Python program writes and a later non-runner command of the call runs by its own name (`./f.sh`) is not traced (no write-target reading of the body) - backlog.py's own SUPERLITE_FLEET_WORKER refusal is the backstop, as docs/hooks.md #706 already says for files a runner reads by convention - cost if wrong: a later earlier-message block only, the backlog command still refuses
- commit T1 98630fe435 Python heredoc body judged as Python
- tests fast passed=34 failed=1 skipped=0 seconds=2.6
- tests fast passed=134 failed=1 skipped=0 seconds=5.6
- tests fast passed=241 failed=0 skipped=0 seconds=11.9
- commit T1 78997046d0 Python heredoc body judged as Python
Ruling: superseded the ./f.sh ruling above - package review (W2) closed it in bl_py: another command whose basename the Python body names right before a quote (open('f.sh','w') then ./f.sh) keeps the block - cost if wrong: a false block for a body string ending in another command's name
- tests full passed=14327 failed=0 skipped=12 seconds=328.6
- tests fast passed=4 failed=0 skipped=0 seconds=26.4
- tests fast passed=36 failed=5 skipped=0 seconds=2.8
- tests fast passed=141 failed=0 skipped=0 seconds=5.8
- commit T1 27c20aa7bb Python heredoc body judged as Python
- tests full passed=14333 failed=0 skipped=12 seconds=341.5
