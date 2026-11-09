# superlite build report

projection: fixed forecast saved at lint 2026-11-09T20:03:41

                         Projected    Actual  Delta
wall-clock (min)               1.1       1.5  +0.4 (+31%)
agent cost (USD, +rework)      0.10      0.43  +0.33 (+326%)
task-minutes                   2.2       2.0  -0.1 (-6%)
agents                           2         4  +2 (+100%)
cost split: agents $0.43, rework $0.00, coordinator n/a, total $0.43
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.1 min)
model mix: sonnet 2 tasks $0.43
quality: tests 5024 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.0     0.5  -0.5 (-49%)     $0.176
T1    sonnet      1.1     1.5  +0.4 (+31%)     $0.258

takeaway: ran 31% slower than projected; cost 326% over; biggest miss T2
