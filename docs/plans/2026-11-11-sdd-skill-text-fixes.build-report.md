# superlite build report

projection: fixed forecast saved at lint 2026-11-11T20:21:44

                         Projected    Actual  Delta
wall-clock (min)               2.4      89.4  +87.0 (+3701%)
agent cost (USD, +rework)      0.14      0.59  +0.45 (+314%)
task-minutes                   3.9       2.6  -1.3 (-34%)
agents                           2         6  +4 (+200%)
cost split: agents $0.44, rework $0.15, coordinator n/a, total $0.59
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (2.4 min)
model mix: sonnet 2 tasks $0.59
quality: tests 6522 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.6  -1.0 (-63%)     $0.085
T1    sonnet      2.4     2.0  -0.3 (-14%)     $0.504  first-time miss

takeaway: ran 3701% slower than projected; cost 314% over; biggest miss T2
