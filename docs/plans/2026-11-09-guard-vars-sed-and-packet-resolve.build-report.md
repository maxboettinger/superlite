# superlite build report

projection: fixed forecast saved at lint 2026-11-09T12:27:34

                         Projected    Actual  Delta
wall-clock (min)               1.2       1.2  -0.0 (-1%)
agent cost (USD, +rework)      0.28      0.56  +0.28 (+98%)
task-minutes                   3.3       1.8  -1.5 (-46%)
agents                           3         4  +1 (+33%)
cost split: agents $0.56, rework $0.00, coordinator n/a, total $0.56
concurrency: peak 2 at once (projected 3); critical path actual T1; projected T1 (1.2 min)
model mix: sonnet 3 tasks $0.56
quality: tests 4680 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.1     0.4  -0.7 (-65%)     $0.128
T2    sonnet      1.0     0.4  -0.6 (-63%)     $0.128
T1    sonnet      1.2     1.0  -0.2 (-14%)     $0.301

takeaway: ran 1% faster than projected; cost 98% over; biggest miss T3
