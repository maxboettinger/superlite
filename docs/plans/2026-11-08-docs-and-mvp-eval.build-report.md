# superlite build report

projection: fixed forecast saved at lint 2026-11-08T00:50:15

                         Projected    Actual  Delta
wall-clock (min)               1.3      11.4  +10.1 (+766%)
agent cost (USD, +rework)      0.01      1.13  +1.11 (+7619%)
task-minutes                   3.4       1.6  -1.8 (-52%)
agents                           3         6  +3 (+100%)
cost split: agents $0.55, rework $0.57, coordinator n/a, total $1.13
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T1 (1.3 min)
model mix: sonnet 3 tasks $1.13
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.3     0.5  -0.8 (-64%)     $0.201
T2    sonnet      1.1     0.6  -0.5 (-46%)     $0.176
T3    sonnet      1.0     0.6  -0.5 (-44%)     $0.748

takeaway: ran 766% slower than projected; cost 7619% over; biggest miss T1
