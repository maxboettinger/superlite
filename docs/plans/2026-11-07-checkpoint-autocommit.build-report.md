# superlite build report

projection: fixed forecast saved at lint 2026-11-07T15:46:44

                         Projected    Actual  Delta
wall-clock (min)               3.0       2.5  -0.6 (-18%)
agent cost (USD, +rework)      0.24      0.45  +0.21 (+90%)
task-minutes                   3.0       2.2  -0.8 (-25%)
agents                           2         4  +2 (+100%)
cost split: agents $0.45, rework $0.00, coordinator n/a, total $0.45
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (3.0 min)
model mix: sonnet 2 tasks $0.45
quality: tests 4052 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.3     0.9  -0.4 (-29%)     $0.152
T1    sonnet      1.7     1.3  -0.4 (-22%)     $0.298

takeaway: ran 18% faster than projected; cost 90% over; biggest miss T2
