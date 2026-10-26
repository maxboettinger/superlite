# superlite build report

projection: fixed forecast saved at lint 2026-10-26T10:24:09 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.8      11.3  +5.4 (+92%)
agent cost (USD, +rework)      0.38      2.15  +1.76 (+459%)
task-minutes                  15.3      20.6  +5.3 (+35%)
agents                           4        34  +30 (+750%)
cost split: agents $1.95, rework $0.19, coordinator $7.81, total $9.96
concurrency: peak 6 at once (projected 4); critical path actual T2; projected T2 (5.8 min)
model mix: haiku 1 tasks $0.01, sonnet 5 tasks $2.14, coordinator opus $7.81
quality: tests 818 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 24

task  model      pred  actual  delta             cost
T2    sonnet      5.8     2.6  -3.3 (-56%)     $0.480
T4    sonnet      3.2     4.1  +0.9 (+27%)     $0.382
T1    sonnet      3.2     3.5  +0.4 (+12%)     $0.460
T3    sonnet      3.1     2.7  -0.4 (-12%)     $0.478
T5    sonnet      n/a     6.9  n/a             $0.342
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 92% slower than projected; cost 459% over; biggest miss T2
