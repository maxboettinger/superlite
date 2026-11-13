# superlite build report

projection: fixed forecast saved at lint 2026-11-13T06:00:31

                         Projected    Actual  Delta
wall-clock (min)               3.2       6.7  +3.6 (+113%)
agent cost (USD, +rework)      0.11      0.29  +0.18 (+164%)
task-minutes                   3.2       0.9  -2.2 (-71%)
agents                           1         4  +3 (+300%)
cost split: agents $0.16, rework $0.13, coordinator n/a, total $0.29
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.2 min)
model mix: sonnet 1 tasks $0.29
quality: tests 8995 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.2     0.9  -2.2 (-71%)     $0.286  first-time miss

takeaway: ran 113% slower than projected; cost 164% over; biggest miss T1
