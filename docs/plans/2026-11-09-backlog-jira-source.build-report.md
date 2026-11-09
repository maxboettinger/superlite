# superlite build report

projection: fixed forecast saved at lint 2026-11-09T08:34:32 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.9  +0.3 (+17%)
agent cost (USD, +rework)      0.29      0.76  +0.47 (+160%)
task-minutes                   2.7       2.7  -0.1 (-3%)
agents                           2         4  +2 (+100%)
cost split: agents $0.76, rework $0.00, coordinator n/a, total $0.76
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 2 tasks $0.76
quality: tests 4534 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.2     0.8  -0.4 (-31%)     $0.303
T1    sonnet      1.6     1.9  +0.3 (+17%)     $0.462

takeaway: ran 17% slower than projected; cost 160% over; biggest miss T2
