# superlite build report

projection: fixed forecast saved at lint 2026-11-11T20:53:45

                         Projected    Actual  Delta
wall-clock (min)               1.6       0.7  -0.9 (-54%)
agent cost (USD, +rework)      0.13      0.24  +0.11 (+83%)
task-minutes                   3.2       1.3  -1.9 (-60%)
agents                           2         4  +2 (+100%)
cost split: agents $0.24, rework $0.00, coordinator n/a, total $0.24
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.6 min)
model mix: sonnet 2 tasks $0.24
quality: tests 6542 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.5  -1.1 (-67%)     $0.087
T1    sonnet      1.6     0.7  -0.9 (-54%)     $0.154

takeaway: ran 54% faster than projected; cost 83% over; biggest miss T2
