# superlite build report

projection: fixed forecast saved at lint 2026-11-12T16:43:42 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.2      30.5  +20.2 (+198%)
agent cost (USD, +rework)      0.75      2.67  +1.92 (+257%)
task-minutes                  84.8      23.1  -61.6 (-73%)
agents                           9        15  +6 (+67%)
cost split: agents $2.18, rework $0.50, coordinator n/a, total $2.67
concurrency: peak 6 at once (projected 9); critical path actual T6; projected T6 (10.2 min)
model mix: sonnet 9 tasks $2.67
quality: tests 7691 passed, 0 failed; first-time pass 7/9 (77%); rework dispatches 4; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     10.0     1.1  -8.8 (-89%)     $0.144
T3    sonnet      9.2     0.6  -8.6 (-93%)     $0.152
T5    sonnet      9.1     0.6  -8.5 (-94%)     $0.161
T1    sonnet      9.0     0.6  -8.4 (-93%)     $0.152
T8    sonnet      9.0     1.1  -7.9 (-87%)     $0.144
(+4 smaller misses; `sl report --json` lists all)

takeaway: ran 198% slower than projected; cost 257% over; biggest miss T2
