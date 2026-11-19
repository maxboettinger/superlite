# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:34:56

                         Projected    Actual  Delta
wall-clock (min)               5.2       0.7  -4.5 (-86%)
agent cost (USD, +rework)      0.19      0.31  +0.12 (+59%)
task-minutes                   9.9       1.2  -8.8 (-88%)
agents                           2         6  +4 (+200%)
cost split: agents $0.31, rework $0.00, coordinator n/a, total $0.31
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (5.2 min)
model mix: sonnet 2 tasks $0.31
quality: tests 12207 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      5.2     0.7  -4.5 (-86%)     $0.196  first-time miss
T1    sonnet      4.7     0.4  -4.3 (-91%)     $0.115

takeaway: ran 86% faster than projected; cost 59% over; biggest miss T2
