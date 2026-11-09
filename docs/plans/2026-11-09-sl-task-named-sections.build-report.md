# superlite build report

projection: fixed forecast saved at lint 2026-11-09T11:30:18

                         Projected    Actual  Delta
wall-clock (min)               1.2       0.7  -0.5 (-40%)
agent cost (USD, +rework)      0.12      0.24  +0.12 (+96%)
task-minutes                   1.2       0.7  -0.5 (-40%)
agents                           1         3  +2 (+200%)
cost split: agents $0.24, rework $0.00, coordinator n/a, total $0.24
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.2 min)
model mix: sonnet 1 tasks $0.24
quality: tests 4641 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.2     0.7  -0.5 (-40%)     $0.237

takeaway: ran 40% faster than projected; cost 96% over; biggest miss T1
