# superlite build report

projection: fixed forecast saved at lint 2026-11-11T13:23:08

                         Projected    Actual  Delta
wall-clock (min)               3.3       2.2  -1.1 (-34%)
agent cost (USD, +rework)      0.31      0.46  +0.15 (+47%)
task-minutes                   4.9       2.6  -2.3 (-47%)
agents                           3         5  +2 (+67%)
cost split: agents $0.46, rework $0.00, coordinator n/a, total $0.46
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T1 > T2 (3.3 min)
model mix: sonnet 3 tasks $0.46
quality: tests 6301 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.6     0.5  -1.1 (-69%)     $0.116
T2    sonnet      1.6     0.9  -0.8 (-48%)     $0.129
T1    sonnet      1.6     1.2  -0.4 (-26%)     $0.212

takeaway: ran 34% faster than projected; cost 47% over; biggest miss T3
