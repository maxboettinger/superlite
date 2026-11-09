# superlite build report

projection: fixed forecast saved at lint 2026-11-09T19:29:26

                         Projected    Actual  Delta
wall-clock (min)               1.5       1.3  -0.2 (-16%)
agent cost (USD, +rework)      0.14      0.35  +0.21 (+150%)
task-minutes                   1.5       1.3  -0.2 (-16%)
agents                           1         3  +2 (+200%)
cost split: agents $0.35, rework $0.00, coordinator n/a, total $0.35
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.5 min)
model mix: sonnet 1 tasks $0.35
quality: tests 5013 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet      1.5     1.3  -0.2 (-16%)     $0.353

takeaway: ran 16% faster than projected; cost 150% over; biggest miss T1
