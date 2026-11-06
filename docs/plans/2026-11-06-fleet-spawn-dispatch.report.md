# superlite build report

projection: fixed forecast saved at lint 2026-11-06T11:28:07 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.2      17.2  +13.0 (+311%)
agent cost (USD, +rework)      0.32      1.52  +1.20 (+374%)
task-minutes                   6.5       3.9  -2.6 (-40%)
agents                           3         6  +3 (+100%)
cost split: agents $1.11, rework $0.41, coordinator n/a, total $1.52
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T2 > T3 (4.2 min)
model mix: sonnet 3 tasks $1.52
quality: tests 3558 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 1

task  model      pred  actual  delta             cost
T3    sonnet      1.9     0.6  -1.2 (-65%)     $0.649
T1    sonnet      2.3     1.3  -1.0 (-44%)     $0.358
T2    sonnet      2.3     2.0  -0.4 (-16%)     $0.512

takeaway: ran 311% slower than projected; cost 374% over; biggest miss T3
