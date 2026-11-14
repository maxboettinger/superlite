# superlite build report

projection: fixed forecast saved at lint 2026-11-14T12:29:30

                         Projected    Actual  Delta
wall-clock (min)               6.2       1.1  -5.1 (-82%)
agent cost (USD, +rework)      0.12      0.27  +0.14 (+117%)
task-minutes                   6.2       1.1  -5.1 (-82%)
agents                           1         3  +2 (+200%)
cost split: agents $0.27, rework $0.00, coordinator n/a, total $0.27
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (6.2 min)
model mix: sonnet 1 tasks $0.27
quality: tests 9733 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.2     1.1  -5.1 (-82%)     $0.269

takeaway: ran 82% faster than projected; cost 117% over; biggest miss T1
