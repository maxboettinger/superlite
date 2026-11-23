# superlite build report

projection: fixed forecast saved at lint 2026-11-23T07:59:55

                         Projected    Actual  Delta
wall-clock (min)               3.6       0.6  -3.0 (-82%)
agent cost (USD, +rework)      0.01      0.17  +0.16 (+2969%)
task-minutes                   3.6       0.6  -3.0 (-82%)
agents                           1         7  +6 (+600%)
cost split: agents $0.17, rework $0.00, coordinator n/a, total $0.17
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.6 min)
model mix: sonnet 1 tasks $0.17
quality: tests 13559 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.6     0.6  -3.0 (-82%)     $0.170

takeaway: ran 82% faster than projected; cost 2969% over; biggest miss T1
