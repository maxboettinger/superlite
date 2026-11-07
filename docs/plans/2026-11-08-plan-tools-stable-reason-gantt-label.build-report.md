# superlite build report

projection: fixed forecast saved at lint 2026-11-08T00:18:52

                         Projected    Actual  Delta
wall-clock (min)               1.5       0.4  -1.1 (-74%)
agent cost (USD, +rework)      0.11      0.20  +0.10 (+87%)
task-minutes                   1.5       0.4  -1.1 (-74%)
agents                           1         3  +2 (+200%)
cost split: agents $0.20, rework $0.00, coordinator n/a, total $0.20
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.5 min)
model mix: sonnet 1 tasks $0.20
quality: tests 4258 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.5     0.4  -1.1 (-74%)     $0.205

takeaway: ran 74% faster than projected; cost 87% over; biggest miss T1
