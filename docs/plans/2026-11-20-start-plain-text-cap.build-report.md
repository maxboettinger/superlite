# superlite build report

projection: fixed forecast saved at lint 2026-11-20T16:56:38

                         Projected    Actual  Delta
wall-clock (min)               4.6       0.5  -4.1 (-90%)
agent cost (USD, +rework)      0.00      0.09  +0.09 (+3064%)
task-minutes                   4.6       0.5  -4.1 (-90%)
agents                           1         3  +2 (+200%)
cost split: agents $0.09, rework $0.00, coordinator n/a, total $0.09
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.6 min)
model mix: sonnet 1 tasks $0.09
quality: tests 13534 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.6     0.5  -4.1 (-90%)     $0.089

takeaway: ran 90% faster than projected; cost 3064% over; biggest miss T1
