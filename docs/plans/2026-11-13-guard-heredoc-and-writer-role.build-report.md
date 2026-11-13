# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:46:26

                         Projected    Actual  Delta
wall-clock (min)               9.8       6.2  -3.6 (-37%)
agent cost (USD, +rework)      0.14      0.87  +0.74 (+541%)
task-minutes                   9.8       5.9  -3.9 (-40%)
agents                           2         3  +1 (+50%)
cost split: agents $0.87, rework $0.00, coordinator n/a, total $0.87
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (9.8 min)
model mix: sonnet 2 tasks $0.87
quality: tests 9239 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.4     0.9  -3.4 (-79%)     $0.141
T2    sonnet      5.4     4.9  -0.5 (-9%)      $0.733  first-time miss

takeaway: ran 37% faster than projected; cost 541% over; biggest miss T1
