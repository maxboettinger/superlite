# superlite build report

projection: fixed forecast saved at lint 2026-11-07T10:56:37

                         Projected    Actual  Delta
wall-clock (min)               1.5       2.1  +0.5 (+33%)
agent cost (USD, +rework)      0.26      0.78  +0.52 (+198%)
task-minutes                   4.3       1.8  -2.6 (-59%)
agents                           3         5  +2 (+67%)
cost split: agents $0.61, rework $0.17, coordinator n/a, total $0.78
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T1 (1.5 min)
model mix: sonnet 3 tasks $0.78
quality: tests 3933 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.5     0.5  -1.0 (-67%)     $0.177
T1    sonnet      1.5     0.7  -0.8 (-52%)     $0.259
T3    sonnet      1.2     0.5  -0.7 (-59%)     $0.344

takeaway: ran 33% slower than projected; cost 198% over; biggest miss T2
