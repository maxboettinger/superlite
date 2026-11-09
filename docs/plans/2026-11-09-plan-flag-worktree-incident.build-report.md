# superlite build report

projection: fixed forecast saved at lint 2026-11-09T10:38:34

                         Projected    Actual  Delta
wall-clock (min)               1.1       0.7  -0.4 (-34%)
agent cost (USD, +rework)      0.17      0.43  +0.26 (+155%)
task-minutes                   2.2       1.2  -1.0 (-45%)
agents                           2         4  +2 (+100%)
cost split: agents $0.43, rework $0.00, coordinator n/a, total $0.43
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.1 min)
model mix: sonnet 2 tasks $0.43
quality: tests 4586 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.1     0.5  -0.6 (-56%)     $0.216
T2    sonnet      1.1     0.7  -0.4 (-34%)     $0.218

takeaway: ran 34% faster than projected; cost 155% over; biggest miss T1
