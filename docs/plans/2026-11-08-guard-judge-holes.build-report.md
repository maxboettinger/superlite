# superlite build report

projection: fixed forecast saved at lint 2026-11-08T13:44:38 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.6       8.3  +3.8 (+82%)
agent cost (USD, +rework)      0.47      1.81  +1.35 (+289%)
task-minutes                   4.6       7.2  +2.7 (+58%)
agents                           3         5  +2 (+67%)
cost split: agents $1.81, rework $0.00, coordinator n/a, total $1.81
concurrency: peak 1 at once (projected 1); critical path actual T1 T2 T3; projected T1 > T2 > T3 (4.6 min)
model mix: sonnet 3 tasks $1.81
quality: tests 67 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.7     2.9  +1.2 (+73%)     $0.734
T2    sonnet      1.3     2.1  +0.8 (+59%)     $0.535
T3    sonnet      1.6     2.3  +0.7 (+42%)     $0.543

takeaway: ran 82% slower than projected; cost 289% over; biggest miss T1
