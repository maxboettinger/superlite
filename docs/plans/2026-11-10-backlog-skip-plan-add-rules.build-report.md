# superlite build report

projection: fixed forecast saved at lint 2026-11-10T23:03:21 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.8      27.0  +25.2 (+1390%)
agent cost (USD, +rework)      0.63      1.41  +0.79 (+126%)
task-minutes                   8.0       4.5  -3.5 (-44%)
agents                           5        11  +6 (+120%)
cost split: agents $1.01, rework $0.40, coordinator n/a, total $1.41
concurrency: peak 4 at once (projected 5); critical path actual T3; projected T3 (1.8 min)
model mix: sonnet 5 tasks $1.41
quality: tests 5775 passed, 0 failed; first-time pass n/a; rework dispatches 4; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      1.8     0.9  -0.9 (-49%)     $0.190
T1    sonnet      1.8     0.9  -0.8 (-46%)     $0.317
T3    sonnet      1.8     1.1  -0.7 (-39%)     $0.553
T4    sonnet      1.3     0.6  -0.7 (-52%)     $0.135
T2    sonnet      1.4     0.9  -0.5 (-33%)     $0.215

takeaway: ran 1390% slower than projected; cost 126% over; biggest miss T5
