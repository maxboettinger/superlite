# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:16:50 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               5.0       2.8  -2.2 (-44%)
agent cost (USD, +rework)      0.18      0.29  +0.12 (+65%)
task-minutes                   5.0       2.8  -2.2 (-44%)
agents                           1         4  +3 (+300%)
cost split: agents $0.29, rework $0.00, coordinator n/a, total $0.29
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (5.0 min)
model mix: sonnet 1 tasks $0.29
quality: tests 10805 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      5.0     2.8  -2.2 (-44%)     $0.292

takeaway: ran 44% faster than projected; cost 65% over; biggest miss T1
