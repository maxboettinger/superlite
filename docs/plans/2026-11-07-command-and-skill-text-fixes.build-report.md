# superlite build report

projection: fixed forecast saved at lint 2026-11-07T10:22:32

                         Projected    Actual  Delta
wall-clock (min)               1.5       0.5  -1.0 (-65%)
agent cost (USD, +rework)      0.01      0.41  +0.40 (+5748%)
task-minutes                   3.1       0.9  -2.1 (-70%)
agents                           2         3  +1 (+50%)
cost split: agents $0.41, rework $0.00, coordinator n/a, total $0.41
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T1 (1.5 min)
model mix: sonnet 2 tasks $0.41
quality: tests 3882 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.5     0.4  -1.1 (-74%)     $0.190
T1    sonnet      1.5     0.5  -1.0 (-66%)     $0.222

takeaway: ran 65% faster than projected; cost 5748% over; biggest miss T2
