# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:58:51 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.2      58.4  +50.2 (+608%)
agent cost (USD, +rework)      0.40      2.72  +2.32 (+585%)
task-minutes                  31.9      10.8  -21.1 (-66%)
agents                           4        24  +20 (+500%)
cost split: agents $1.96, rework $0.75, coordinator $0.66 (31 turns, context median 55.8k, peak 68.2k; session $0.66), coordinator per task $0.08 (target $1.00), total $3.38
concurrency: peak 5 at once (projected 4); critical path actual T1; projected T1 (8.2 min)
model mix: sonnet 8 tasks $2.72, coordinator sonnet $0.66
quality: tests 12288 passed, 0 failed; first-time pass 4/8 (50%); rework dispatches 5; open incidents 12

task  model      pred  actual  delta             cost
T4    sonnet      7.7     0.7  -7.0 (-91%)     $0.333  first-time miss
T1    sonnet      8.2     1.5  -6.7 (-82%)     $0.620  first-time miss
T5    sonnet      7.8     1.8  -6.0 (-77%)     $0.328
T3    sonnet      8.2     2.1  -6.0 (-74%)     $0.383  first-time miss
T2    sonnet      n/a     1.1  n/a             $0.203
(+3 smaller misses; `sl report --json` lists all)

takeaway: ran 608% slower than projected; cost 585% over; biggest miss T4
