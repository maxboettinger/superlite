# superlite build report

projection: fixed forecast saved at lint 2026-11-09T14:41:15

                         Projected    Actual  Delta
wall-clock (min)               1.0      15.1  +14.2 (+1436%)
agent cost (USD, +rework)      0.00      0.37  +0.37 (+8564%)
task-minutes                   1.0       0.6  -0.4 (-44%)
agents                           1         4  +3 (+300%)
cost split: agents $0.21, rework $0.16, coordinator n/a, total $0.37
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.0 min)
model mix: sonnet 1 tasks $0.37
quality: tests 4748 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.0     0.6  -0.4 (-44%)     $0.373

takeaway: ran 1436% slower than projected; cost 8564% over; biggest miss T1
