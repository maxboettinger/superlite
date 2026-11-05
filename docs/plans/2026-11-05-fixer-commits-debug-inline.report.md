# superlite build report

projection: fixed forecast saved at lint 2026-11-05T15:10:18

                         Projected    Actual  Delta
wall-clock (min)               1.7       1.1  -0.6 (-38%)
agent cost (USD, +rework)      0.01      0.30  +0.29 (+3571%)
task-minutes                   3.4       1.7  -1.6 (-49%)
agents                           2         9  +7 (+350%)
cost split: agents $0.30, rework $0.00, coordinator $0.18 (12 turns, context median 21.3k, peak 26.6k; session $0.18), total $0.48
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (1.7 min)
model mix: sonnet 2 tasks $0.30, coordinator sonnet $0.18
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.7     0.7  -1.0 (-59%)     $0.118
T1    sonnet      1.7     1.1  -0.6 (-38%)     $0.183

takeaway: ran 38% faster than projected; cost 3571% over; biggest miss T2
