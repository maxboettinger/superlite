# superlite build report

projection: fixed forecast saved at lint 2026-11-09T20:52:29

                         Projected    Actual  Delta
wall-clock (min)               1.5       1.2  -0.3 (-20%)
agent cost (USD, +rework)      0.14      0.28  +0.15 (+108%)
task-minutes                   1.5       1.2  -0.3 (-20%)
agents                           1         3  +2 (+200%)
cost split: agents $0.28, rework $0.00, coordinator n/a, total $0.28
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.5 min)
model mix: sonnet 1 tasks $0.28
quality: tests 5106 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.5     1.2  -0.3 (-20%)     $0.282

takeaway: ran 20% faster than projected; cost 108% over; biggest miss T1
