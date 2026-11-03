# superlite build report

projection: fixed forecast saved at lint 2026-10-26T10:24:09 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.8      13.8  +8.0 (+136%)
agent cost (USD, +rework)      0.38      1.59  +1.21 (+314%)
task-minutes                  15.3      27.0  +11.7 (+76%)
agents                           4        14  +10 (+250%)
cost split: agents $1.59, rework $0.00, coordinator $23.20, total $24.79
concurrency: peak 4 at once (projected 4); critical path actual T3; projected T2 (5.8 min)
model mix: haiku 1 tasks $0.02, sonnet 5 tasks $1.57, coordinator fable $23.20
quality: tests 3 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      3.1    13.3  +10.3 (+337%)   $0.417
T2    sonnet      5.8     1.5  -4.3 (-74%)     $0.076
T1    sonnet      3.2     2.9  -0.3 (-10%)     $0.324
T6    sonnet      n/a     6.0  n/a             $0.638
T7    haiku       n/a     2.2  n/a             $0.025
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 136% slower than projected; cost 314% over; biggest miss T3
