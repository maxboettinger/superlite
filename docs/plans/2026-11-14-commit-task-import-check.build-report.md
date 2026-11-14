# superlite build report

projection: fixed forecast saved at lint 2026-11-14T23:15:09

                         Projected    Actual  Delta
wall-clock (min)               3.2       2.8  -0.4 (-12%)
agent cost (USD, +rework)      0.09      0.17  +0.09 (+98%)
task-minutes                   3.2       2.8  -0.4 (-12%)
agents                           1         3  +2 (+200%)
cost split: agents $0.17, rework $0.00, coordinator n/a, total $0.17
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.2 min)
model mix: sonnet 1 tasks $0.17
quality: tests 9934 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.2     2.8  -0.4 (-12%)     $0.174

takeaway: ran 12% faster than projected; cost 98% over; biggest miss T1
