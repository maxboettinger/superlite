# superlite build report

projection: fixed forecast saved at lint 2026-11-11T20:23:17

                         Projected    Actual  Delta
wall-clock (min)               1.6       0.8  -0.8 (-50%)
agent cost (USD, +rework)      0.17      0.26  +0.08 (+48%)
task-minutes                   3.2       1.3  -1.9 (-59%)
agents                           2         4  +2 (+100%)
cost split: agents $0.26, rework $0.00, coordinator n/a, total $0.26
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 2 tasks $0.26
quality: tests 6528 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.5  -1.1 (-67%)     $0.131
T1    sonnet      1.6     0.8  -0.8 (-50%)     $0.125

takeaway: ran 50% faster than projected; cost 48% over; biggest miss T2
