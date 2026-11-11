# superlite build report

projection: fixed forecast saved at lint 2026-11-11T08:03:03

                         Projected    Actual  Delta
wall-clock (min)               1.6      25.6  +24.0 (+1539%)
agent cost (USD, +rework)      0.11      0.36  +0.25 (+226%)
task-minutes                   1.6       0.9  -0.7 (-44%)
agents                           1         4  +3 (+300%)
cost split: agents $0.19, rework $0.17, coordinator n/a, total $0.36
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 1 tasks $0.36
quality: tests 3 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.6     0.9  -0.7 (-44%)     $0.356

takeaway: ran 1539% slower than projected; cost 226% over; biggest miss T1
