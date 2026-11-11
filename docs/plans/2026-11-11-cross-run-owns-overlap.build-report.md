# superlite build report

projection: fixed forecast saved at lint 2026-11-11T16:15:12

                         Projected    Actual  Delta
wall-clock (min)               4.0       2.6  -1.4 (-35%)
agent cost (USD, +rework)      0.44      0.66  +0.22 (+50%)
task-minutes                   7.2       3.5  -3.6 (-51%)
agents                           4         6  +2 (+50%)
cost split: agents $0.66, rework $0.00, coordinator n/a, total $0.66
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T3 (4.0 min)
model mix: sonnet 4 tasks $0.66
quality: tests 6475 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      1.6     0.6  -1.0 (-64%)     $0.096
T1    sonnet      2.3     1.3  -1.0 (-44%)     $0.249
T2    sonnet      1.6     0.7  -0.9 (-57%)     $0.118
T3    sonnet      1.6     1.0  -0.7 (-41%)     $0.192

takeaway: ran 35% faster than projected; cost 50% over; biggest miss T4
