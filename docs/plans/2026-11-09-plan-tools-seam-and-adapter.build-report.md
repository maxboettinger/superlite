# superlite build report

projection: fixed forecast saved at lint 2026-11-09T15:40:08

                         Projected    Actual  Delta
wall-clock (min)               2.1       2.5  +0.4 (+17%)
agent cost (USD, +rework)      0.17      0.55  +0.38 (+222%)
task-minutes                   2.1       2.2  +0.1 (+4%)
agents                           2         4  +2 (+100%)
cost split: agents $0.55, rework $0.00, coordinator n/a, total $0.55
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (2.1 min)
model mix: sonnet 2 tasks $0.55
quality: tests 4777 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.1     1.4  +0.2 (+22%)     $0.327
T1    sonnet      1.0     0.9  -0.2 (-16%)     $0.227

takeaway: ran 17% slower than projected; cost 222% over; biggest miss T2
