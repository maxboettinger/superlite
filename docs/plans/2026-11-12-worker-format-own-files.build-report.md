# superlite build report

projection: fixed forecast saved at lint 2026-11-12T05:08:39

                         Projected    Actual  Delta
wall-clock (min)               1.5       0.4  -1.1 (-76%)
agent cost (USD, +rework)      0.00      0.08  +0.08 (+2162%)
task-minutes                   1.5       0.4  -1.1 (-76%)
agents                           1         3  +2 (+200%)
cost split: agents $0.08, rework $0.00, coordinator n/a, total $0.08
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.5 min)
model mix: sonnet 1 tasks $0.08
quality: tests 6843 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.5     0.4  -1.1 (-76%)     $0.083

takeaway: ran 76% faster than projected; cost 2162% over; biggest miss T1
