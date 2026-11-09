# superlite build report

projection: fixed forecast saved at lint 2026-11-09T13:46:15 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.8      14.7  +11.9 (+430%)
agent cost (USD, +rework)      0.70      1.28  +0.58 (+82%)
task-minutes                   5.8       3.2  -2.6 (-45%)
agents                           4         6  +2 (+50%)
cost split: agents $0.98, rework $0.30, coordinator n/a, total $1.28
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T1 > T4 (2.8 min)
model mix: sonnet 4 tasks $1.28
quality: tests 4746 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.8     0.8  -1.0 (-55%)     $0.208
T1    sonnet      1.6     0.9  -0.8 (-48%)     $0.635
T4    sonnet      1.1     0.7  -0.4 (-37%)     $0.157
T3    sonnet      1.2     0.8  -0.4 (-31%)     $0.279

takeaway: ran 430% slower than projected; cost 82% over; biggest miss T2
