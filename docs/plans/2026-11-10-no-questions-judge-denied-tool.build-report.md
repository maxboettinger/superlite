# superlite build report

projection: fixed forecast saved at lint 2026-11-10T12:49:53

                         Projected    Actual  Delta
wall-clock (min)               1.1       0.5  -0.6 (-57%)
agent cost (USD, +rework)      0.00      0.10  +0.09 (+2192%)
task-minutes                   1.1       0.5  -0.6 (-57%)
agents                           1         3  +2 (+200%)
cost split: agents $0.10, rework $0.00, coordinator n/a, total $0.10
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (1.1 min)
model mix: sonnet 1 tasks $0.10
quality: tests 5558 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.1     0.5  -0.6 (-57%)     $0.096

takeaway: ran 57% faster than projected; cost 2192% over; biggest miss T1
