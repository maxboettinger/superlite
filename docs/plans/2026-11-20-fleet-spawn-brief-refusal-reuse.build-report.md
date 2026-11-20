# superlite build report

projection: fixed forecast saved at lint 2026-11-20T16:26:48

                         Projected    Actual  Delta
wall-clock (min)               3.6       0.7  -2.9 (-80%)
agent cost (USD, +rework)      0.08      0.14  +0.06 (+83%)
task-minutes                   3.6       0.7  -2.9 (-80%)
agents                           1         3  +2 (+200%)
cost split: agents $0.14, rework $0.00, coordinator n/a, total $0.14
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.6 min)
model mix: sonnet 1 tasks $0.14
quality: tests 13531 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.6     0.7  -2.9 (-80%)     $0.142

takeaway: ran 80% faster than projected; cost 83% over; biggest miss T1
