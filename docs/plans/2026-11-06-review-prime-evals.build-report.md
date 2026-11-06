# superlite build report

projection: fixed forecast saved at lint 2026-11-06T18:48:20

                         Projected    Actual  Delta
wall-clock (min)               1.7       6.9  +5.2 (+300%)
agent cost (USD, +rework)      0.10      0.71  +0.61 (+621%)
task-minutes                   4.6       1.4  -3.2 (-70%)
agents                           3         5  +2 (+67%)
cost split: agents $0.46, rework $0.25, coordinator n/a, total $0.71
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T3 (1.7 min)
model mix: sonnet 3 tasks $0.71
quality: tests 3755 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     0.3  -1.2 (-79%)     $0.364
T2    sonnet      1.4     0.3  -1.0 (-76%)     $0.114
T3    sonnet      1.7     0.8  -1.0 (-56%)     $0.230

takeaway: ran 300% slower than projected; cost 621% over; biggest miss T1
